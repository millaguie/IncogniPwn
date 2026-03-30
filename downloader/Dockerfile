FROM mcr.microsoft.com/dotnet/sdk:8.0 AS builder

RUN dotnet tool install --global haveibeenpwned-downloader

FROM mcr.microsoft.com/dotnet/runtime:8.0

RUN apt-get update && apt-get install -y --no-install-recommends rsync && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.dotnet/tools /root/.dotnet/tools
ENV PATH="/root/.dotnet/tools:${PATH}"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
