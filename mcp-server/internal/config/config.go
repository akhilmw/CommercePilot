package config

import "os"

type Config struct {
	Port        string
	DatabaseURL string
}

func Load() Config {
	port := os.Getenv("COMMERCEPILOT_MCP_PORT")
	if port == "" {
		port = "8081"
	}
	databaseURL := os.Getenv("COMMERCEPILOT_MCP_DATABASE_URL")
	if databaseURL == "" {
		databaseURL = "postgresql://commercepilot:commercepilot@localhost:5432/commercepilot?sslmode=disable"
	}

	return Config{
		Port:        port,
		DatabaseURL: databaseURL,
	}
}
