package httpserver

import (
	"encoding/json"
	"log/slog"
	"net/http"
)

type healthResponse struct {
	Status  string `json:"status"`
	Service string `json:"service"`
}

func New(logger *slog.Logger, mcpHandler http.Handler) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", func(writer http.ResponseWriter, _ *http.Request) {
		writer.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(writer).Encode(healthResponse{
			Status:  "healthy",
			Service: "commercepilot-go-service",
		}); err != nil {
			logger.Error("failed to encode health response", "error", err)
		}
	})
	mux.Handle("/mcp", mcpHandler)

	return mux
}
