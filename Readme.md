# AWS Beanstalk - FastAPI with SocketIO

```bash
eb init -p docker fastapi-socketio
eb create docker-env --elb-type application
```

## Logging

This project uses [loguru](https://pypi.org/project/loguru/).
It logs human readable logs to `stdout` and JSON logs to `stderr`. This allows you to both read the container logs directly and write and parse them to something like OpenSearch or Elasticsearch.

To view either with docker:

```shell
# Human readable
docker logs beanstalk-fastapi-app-1 2> /dev/null

# JSON
docker logs beanstalk-fastapi-app-1 > /dev/null
```

## Alembic

### Initialized

1. Initialize

    ```shell
    alembic init -t async migrations
    ```

2. Create first revision

    ```shell
    alembic revision --autogenerate -m "000 - init"
    ```
