FROM golang:1.25-alpine AS builder

WORKDIR /src

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /commercepilot-mcp ./cmd/server

FROM alpine:3.22

RUN apk add --no-cache ca-certificates

COPY --from=builder /commercepilot-mcp /usr/local/bin/commercepilot-mcp

EXPOSE 8081

CMD ["commercepilot-mcp"]
