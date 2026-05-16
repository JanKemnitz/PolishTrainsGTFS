# Stage 1: Build the Go realtime generator
FROM golang:1.26-alpine AS go-builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -o /app/realtime_gen ./polish_trains_gtfs/realtime/cmd/main.go

# Stage 2: Final image with Python and Go binary
FROM python:3.14-slim
WORKDIR /app

# Install runtime system dependencies
RUN apt-get update \
	&& apt-get install -y --no-install-recommends libexpat1 \
	&& rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .
COPY --from=go-builder /app/realtime_gen /app/realtime_gen

# Create output directory for served files
RUN mkdir -p /app/output

# Copy and prepare the entrypoint script
COPY prop/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose the port for the simple Python web server
EXPOSE 8081

ENTRYPOINT ["/app/entrypoint.sh"]
