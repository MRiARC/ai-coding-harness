FROM golang:1.26-alpine AS build
WORKDIR /src
COPY gateway/go.mod gateway/go.sum ./
RUN go mod download
COPY gateway/ ./
RUN CGO_ENABLED=0 go build -o /foreman-gateway .

FROM alpine:3.20
COPY --from=build /foreman-gateway /usr/local/bin/foreman-gateway
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/foreman-gateway"]
