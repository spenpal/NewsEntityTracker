# News Entity Tracker

**News Entity Tracker** is a real-time Big Data analysis project focused on extracting and analyzing named entities from current news articles using Spark, Kafka, and the ELK stack.

![Example Bar Plots in Kibana](/docs/example_plots.png)

You can read about my summarized findings [here](/docs/report.pdf).

This [project](/docs/instructions.pdf) was completed in the following setting:

-   University: [University of Texas at Dallas](https://www.utdallas.edu/)
-   Course: [CS 6350 (Big Data Management and Analytics)](https://catalog.utdallas.edu/2023/graduate/courses/cs6350)
-   Professor: [Dr. Anurag Nagar](https://scholar.google.com/citations?user=GNo6nEAAAAAJ&hl=en)
-   Semester: Fall 2023

## Data Flow

1. Get news data from NewsAPI and send it to the **RawDataTopic** (`newsapi.py`)
2. Get news data from **RawDataTopic** by uploading it to a `PySpark` streaming dataframe, transform the data to keep a running count of named entities found, and send these tallies to the **NamedEntitiesCountTopic** in a JSON format (_ex: {"named_entity":"Tesla","count":"4"}_) (`streamer.py`).
3. Setup `Logstash` to parse the data stored in **NamedEntitiesCountTopic** and send it to a pre-defined index in `Elasticsearch`.
4. Use `Kibana` to explore the data and create bar plots of the top 10 named entities by counts, in several intervals.

## Setup

The project setup is done locally. These instructions assume you're on a Linux environment.

1.  Install [Apache Kafka](https://kafka.apache.org/quickstart) and start Zookeeper and Kafka servers.

    -   Create 2 Kafka topics: `RawDataTopic` and `NamedEntitiesCountTopic`.
        -   `~/kafka_*/bin/kafka-topics.sh --create --topic <topic-name> --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1`
    -   To see what topics are available on your Kafka server, you can use the following command: `~/kafka_*/bin/kafka-topics.sh --list --bootstrap-server localhost:9092`

1.  Install [Apache Spark](https://spark.apache.org/downloads.html).

    -   [Article Help (For Ubuntu)](https://www.virtono.com/community/tutorial-how-to/how-to-install-apache-spark-on-ubuntu-22-04-and-centos/).

1.  Install [Elasticsearch, Kibana, and Logstash](https://www.elastic.co/downloads/).

    -   Article Helps
        -   [Installation and Setup of Elasticsearch](https://www.cherryservers.com/blog/install-elasticsearch-ubuntu)
        -   [Installation and Setup of Logstash](https://devconnected.com/how-to-install-logstash-on-ubuntu-18-04-and-debian-9/#3_-_Install_Logstash_with_apt)
        -   [Logstash Directory Layout](https://www.elastic.co/guide/en/logstash/current/dir-layout.html)
    -   In `/etc/elasticsearch/elasticsearch.yml`, do the following:

        ```
        # Set this to "localhost"
        network.host: localhost

        # Set this to false, ONLY if you face authentication issues with Elasticsearch
        xpack.security.enabled: false
        ```

    -   Make sure the user and group of the `/usr/share/logstash/data` folder is by `logstash`. If not, use the following commands to fix it:
        1.  `chown -R logstash.logstash /usr/share/logstash`
        1.  `chmod 777 /usr/share/logstash/data`

1.  Get an API Key from [NewsAPI](https://newsapi.org/).
1.  Install project dependencies.

    -   Additionally, download spaCy model: `python -m spacy download en_core_web_sm`
    -   **NOTE**: For this project, I am using **Python 3.11**, however **Python 3.9+** should work.

1.  Setup environment variables.

    -   Rename `config/config.env` to `config/.env` and fill in the variables.

1.  Setup Logstash script.

    -   Copy `config/logstash.conf` to the config directory of `Logstash`.
    -   Example: `cp config/logstash.conf /etc/logstash/conf.d/`

## Running The Project

1. Start up Elasticsearch and Kibana services.
    - `sudo service elasticsearch start`
        - To check if Elasticsearch has started: `sudo service elasticsearch status`
        - Verify Elasticsearch is working: `curl http://localhost:9200/`
    - `sudo service kibana start`
        - To check if Kibana has started: `sudo service kibana status`
1. Create an index in Elasticsearch for named entity data to be sent to.
    - `curl -X PUT "localhost:9200/named_entities?pretty`
1. Go to home directory of `Logstash` and run Logstash with the configuration file: `bin/logstash -f /etc/logstash/conf.d/logstash.conf`
    - To find the home directory of **Logstash**: `whereis -b logstash`
1. Start the streaming script by submitting it to the Spark cluster.
    - `spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:<your-spark-version> src/streamer.py`
1. Start the NewsAPI script: `python src/newsapi.py`
    - It is currently configured to fetch from the API every 60 mins, as fetching any earlier will result in duplicate news.
1. Data should slowly start populating in Elasticsearch. You can access the data in Kibana at [http://localhost:5601/](http://localhost:5601/).
    - Currently, the **count** field in Kibana is of a _text_ property, so aggregations won't work. In order to do proper visualizations (_like bar plots_), you need to re-index the `count` field and cast it to an _integer_.
        1. Create conversion pipeline.
            - `curl -XPUT "http://localhost:9200/_ingest/pipeline/convert_pipeline" -H 'Content-Type: application/json' -d '{"description":"Converts count field to integer","processors":[{"convert":{"field":"count","type":"integer"}}]}'`
        1. Re-index.
            - `curl -XPOST "http://localhost:9200/_reindex" -H 'Content-Type: application/json' -d '{"source":{"index":"named_entities"},"dest":{"index":"named_entities_converted","pipeline":"convert_pipeline"}}'`
