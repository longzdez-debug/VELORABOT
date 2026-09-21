FROM rust:1.89-bookworm AS build
WORKDIR /src
COPY Cargo.toml .
COPY apps/api/Cargo.toml apps/api/Cargo.toml
COPY apps/api/src apps/api/src
COPY apps/api/migrations apps/api/migrations
RUN cargo build --release -p velora-api
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/target/release/velora-api /usr/local/bin/velora-api
EXPOSE 8080
CMD ["velora-api"]
