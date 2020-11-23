FROM python:3.7-slim-stretch

EXPOSE 5000

# Copy only requirements.txt so that we only execute the expensive dependency install when the dependencies actually change.
# This results in much faster build time, and we're not constantly pulling down packages.
COPY requirements.txt /requirements.txt

# Install dependencies
RUN pip install -r requirements.txt \
      --no-cache-dir

COPY . /app
RUN chmod +x /app/*.sh
WORKDIR /app

ENTRYPOINT ["/app/entrypoint.sh"]
