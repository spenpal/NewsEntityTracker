import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from kafka import KafkaProducer

# Load .env variables
current_directory = Path.cwd()
env_path = current_directory.parent.joinpath("config", ".env")
load_dotenv(env_path)

kafka_broker_url = os.getenv("KAFKA_BROKER_URL")
newsapi_api_key = os.getenv("NEWSAPI_API_KEY")
topic1 = os.getenv("TOPIC1")


def fetch_and_send_news(sent_articles_filename, sent_articles, kafka_topic, producer):
    # Latest news articles from the News API
    endpoint = "https://newsapi.org/v2/top-headlines"

    # Set parameters for the News API request
    params = {
        "apiKey": newsapi_api_key,
        "language": "en",
        "country": "us",
        "pageSize": 100,
    }

    # Make a request to the News API
    response = requests.get(endpoint, params=params)

    new_articles = set()  # store unseen articles

    if response.status_code == 200:
        # Parse the JSON response
        news_articles = response.json()

        # Send each article to Kafka
        for article in news_articles["articles"]:
            if article["content"] and article["url"] not in sent_articles:
                producer.send(kafka_topic, value=article["content"])
                sent_articles.add(article["url"])
                new_articles.add(article["url"])
                print(f"Sent article to Kafka: {article['title']}")
        print("<---------------- WAITING 60 MINUTES FOR NEW ARTICLES ---------------->")
    else:
        print(f"Error fetching news data. Status code: {response.status_code}")

    # Save the set of sent articles to the file
    with open(sent_articles_filename, "a") as f:
        for article_url in new_articles:
            f.write(f"{article_url}\n")


def main():
    # Create a Kafka producer
    producer = KafkaProducer(
        bootstrap_servers=kafka_broker_url,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    # Kafka topic for raw news data
    kafka_topic = topic1

    # Keep track of what articles have been sent
    sent_articles_filename = "sent_articles.txt"
    if os.path.exists(sent_articles_filename):
        with open(sent_articles_filename) as f:
            sent_articles = set(f.read().splitlines())
    else:
        sent_articles = set()

    try:
        # Fetch and send news every 60 minutes
        while True:
            fetch_and_send_news(
                sent_articles_filename, sent_articles, kafka_topic, producer
            )
            time.sleep(60 * 60)
    except KeyboardInterrupt:
        print("Exiting...")
        try:
            # Close the Kafka producer
            if producer:
                producer.close()
        except Exception as e:
            print(f"Error during cleanup: {e}")


if __name__ == "__main__":
    main()
