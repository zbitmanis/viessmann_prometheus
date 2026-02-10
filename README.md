# Viessmann Exporter

A lightweight Prometheus exporter to collect metrics from a Viessmann gas boiler using the Viessmann API.

## Table of Contents

- [Introduction](#introduction)
- [Installation](#installation)
- [Usage](#usage)
- [Features](#features)
- [Configuration](#configuration)
- [Dependencies](#dependencies)
- [Examples](#examples)
- [Reverse Proxy (NGINX)](#reverse-proxy-nginx)
- [Troubleshooting](#troubleshooting)
- [Contributors](#contributors)
- [License](#license)

## Introduction

**Viessmann Exporter** is a Prometheus-compatible exporter that retrieves real-time metrics from a Viessmann gas boiler via their official API. It provides an easy way to monitor your heating system and integrate it into any Prometheus-based monitoring stack.

This project uses OAuth2 authentication to securely access the Viessmann API, encapsulated in the `viessmann_oauth` submodule.

## Installation

### Prerequisites

- Python 3.8+
- [pip](https://pip.pypa.io/en/stable/)
- [Uvicorn](https://www.uvicorn.org/) for serving the API

### Steps

1. Clone the repository:

    ```bash
    git clone git@github.com:zbitmanis/viessmann_exporter.git
    cd viessmann_exporter
    ```

2. (Optional) Create a virtual environment:

    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

3. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

## Usage

Start the Prometheus exporter server using:

```bash
uvicorn viessmann_exporter:viessmann_exporter --host 0.0.0.0 --port 9000
```

Once running, the exporter will expose metrics and callback url at:

```
http://<your-host>:9000/metrics
http://<your-host>:9000/oauth/callback
```

## Features

- OAuth2 authentication via Viessmann developer API
- Metrics export in Prometheus format
- Modular design using `viessmann_oauth` as an authentication submodule
- Simple deployment with Uvicorn

## Configuration

You will need the following environment variables or configuration values (check `viessmann_oauth.py` for details):

- `VIESSMANN_CLIENT_ID`
- `VIESSMANN_CLIENT_SECRET`
- `VIESSMANN_REDIRECT_URI`

Set these in your environment before running the exporter:

```bash
export VIESSMANN_CLIENT_ID="your-client-id"
export VIESSMANN_CLIENT_SECRET="your-client-secret"
export VIESSMANN_REDIRECT_URI="https://your.domain.com/callback"
```

## Dependencies

Main dependencies include:

- `httpx`
- `uvicorn`
- `prometheus_client`
- `pydantic`
- `fastapi`

Full list can be found in `requirements.txt`.

## Examples

### Start Exporter

```bash
uvicorn viessmann_exporter.main:app --host 0.0.0.0 --port 9000
```

### Prometheus Scrape Configuration

```yaml
scrape_configs:
  - job_name: 'viessmann'
    static_configs:
      - targets: ['your.domain.com/metrics']
```

## Reverse Proxy (NGINX)

Below is a production-ready NGINX configuration used to reverse proxy the Viessmann exporter, enforce HTTPS, restrict access to internal networks, and handle OAuth callback routing.

```nginx
# Preferable to manage file by configuration management tool like Ansible
# HTTP Redirect to HTTPS
server {
    listen 80;
    server_name your.domain.com;

    return 301 "https://$host$request_uri";
}

# HTTPS Server Block
server {
    listen 443 ssl;
    server_name your.domain.com;

    ssl_certificate     /path/to/your.domain.com/fullchain.pem;
    ssl_certificate_key /path/to/your.domain.com/privkey.pem;

    root _;

    # Allow only internal/private networks 
    # Allow only access from your private network CIDR  e.g. 172.16.x.x/24
    allow 192.168.0.0/16;
    allow 10.0.0.0/8;
    allow 172.16.0.0/12;
    allow 127.0.0.1;
    deny all;

    # OAuth Callback for Viessmann 
    # The callback FQDN should be registered within Viessmann Developer portal

    localtion /callback {
    
    proxy_set_header Accept-Encoding "";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_pass http://127.0.0.1:9000/oauth/callback$is_args$args;
    }
    
    # Login endpoint to auth with Viessmann dev portal
    # The endpoint should be accessed by browser
    localtion /login {
    
    proxy_set_header Accept-Encoding "";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    proxy_pass http://127.0.0.1:9000/oauth/login;
    } 
    
    location ~ ^/(success|fail)/?$ {
    
    proxy_set_header Accept-Encoding "";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    proxy_pass http://127.0.0.1:9000;
    }

    # Optional endpoint for debugging purposes
    # Make it accessible only from safe location e.g. localhost

    #location ~ ^/debug/token/(status|raw)$ {
    #
    #allow 127.0.0.1;
    #deny all;
    #
    #proxy_set_header Accept-Encoding "";
    #proxy_set_header Host $host;
    #proxy_set_header X-Real-IP $remote_addr;
    #proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    #proxy_set_header X-Forwarded-Proto $scheme;
    #add_header X-Debug-location "viessmann-debug" always;
    #
    #proxy_pass http://127.0.0.1:9000;
    #}
}
```

> 🔒 This configuration:
> - Redirects HTTP to HTTPS
> - Limits access to private/internal IP ranges
> - Proxies the Viessmann OAuth callback path to your local Uvicorn server



## Podman Support

You can run the Viessmann Exporter in a rootless Podman container for secure, systemd-managed deployment.

### Build the Image

```bash
podman build -t viessmann-prometheus .
```

### Run the Container

```bash
podman run -d \
  -p 9000:9000 \
  -e VIESSMANN_CLIENT_ID="your-client-id" \
  -e VIESSMANN_CLIENT_SECRET="your-client-secret" \
  -e VIESSMANN_REDIRECT_URI="https://your.domain.com/callback"\
  --name viessmann-prometheus \
  viessmann-prometheus
```

### Optional: Using an `.env` File

```bash
podman run --env-file .env -p 9000:9000 viessmann-prometheus
```
```bash
source env.sh
podman run --env --env 'VIESSMANN* -p 9000:9000 viessmann-prometheus
```

## Running with systemd (Podman)

To manage the container as a service, you can generate a `systemd` unit file:

```bash
podman generate systemd --name viessmann-prometheus --files --restart-policy=always
```

This will create a file like `container-viessmann-exporter.service`.

Copy it to your user systemd directory:

```bash
mkdir -p ~/.config/systemd/user/
mv container-viessmann-prometheus.service ~/.config/systemd/user/
systemctl --user daemon-reexec
systemctl --user daemon-reload
systemctl --user enable --now container-viessmann-prometheus.service
```

To check status:

```bash
systemctl --user status container-viessmann-prometheus.service
```

> ✅ Tip: For root services, use `/etc/systemd/system/` and `sudo systemctl` instead.



## Metrics Exposed

The Viessmann Exporter exposes Prometheus-compatible metrics that reflect the current operational state and performance of your Viessmann gas boiler.

Examples include:

- `viessmann_boiler_temperature_celsius` – Current boiler water temperature in °C
- `viessmann_outside_temperature_celsius` – Current outdoor temperature
- `viessmann_gas_consumption_total` – Total gas consumption in m³

> Metrics are automatically labeled with system-specific metadata (e.g., installation ID).

## Configuration Options

The Viessmann Exporter is configured via environment variables:

| Variable                  | Description                               | Required | Default |
|---------------------------|-------------------------------------------|----------|---------|
| `VIESSMANN_CLIENT_ID`     | Viessmann API OAuth2 client ID            | ✅ Yes   | —       |
| `VIESSMANN_CLIENT_SECRET` | Viessmann API OAuth2 client secret        | ✅ Yes   | —       |
| `VIESSMANN_REDIRECT_URI` |   Viessmann API OAuth2 callback url  e.g. "<https://your.domain.com/callback"\`>  | ✅ Yes   | —       |
| `EXPORTER_PORT`           | Port to expose metrics on                 | ❌ No    | `9000`  |

Set these variables directly or pass them via a `.env` file.

## Security Considerations

- **Do not expose `/metrics` to the public internet without protection.**
- **Do not expose `/login` to the public internet without protection.**
- **Do not expose `/debug` to the public internet without protection.**
- Use NGINX or another reverse proxy with **HTTP Basic Auth** and/or IP allowlisting.
- For internal-only use, firewall the port (e.g., 9000) to local subnets.

## Prometheus Scrape Configuration

Add the following to your Prometheus `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'viessmann_exporter'
    scrape_interval: 30s
    metrics_path: /metrics
    static_configs:
      - targets: ['your.domain.com:9000']
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
```


## Troubleshooting

- **Authentication Errors**: Ensure your Viessmann API credentials are correct and exported as environment variables.
- **Empty Metrics**: Check if your boiler is online and the API scope includes access to required features.
- **Port Conflicts**: Ensure port 9000 is not in use by another process.
- **NGINX 502 Errors**: Ensure the Uvicorn server is running and accessible at the configured port.

## Contributors

- **Andris Zbitkovskis** — Creator and maintainer

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
