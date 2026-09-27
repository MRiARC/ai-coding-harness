package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func fakeOrchestrator(t *testing.T, status int, body map[string]any) *httptest.Server {
	t.Helper()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		_ = json.NewEncoder(w).Encode(body)
	}))
}

func TestHealthEndpoint(t *testing.T) {
	gateway := NewGateway(LoadConfig(), nil)
	server := httptest.NewServer(gateway.Handler())
	defer server.Close()

	response, err := http.Get(server.URL + "/api/health")
	if err != nil {
		t.Fatalf("health request failed: %v", err)
	}
	defer response.Body.Close()
	var body map[string]any
	if err := json.NewDecoder(response.Body).Decode(&body); err != nil {
		t.Fatalf("decode failed: %v", err)
	}
	if body["status"] != "ok" || body["service"] != "gateway" {
		t.Fatalf("unexpected health body: %v", body)
	}
}

func TestCreateTaskProxiesAndRecords(t *testing.T) {
	upstream := fakeOrchestrator(t, http.StatusOK, map[string]any{
		"success": true, "outcome": "VERIFIED", "evidence_path": "/tmp/evidence",
	})
	defer upstream.Close()

	gateway := NewGateway(Config{OrchestratorURL: upstream.URL}, nil)
	server := httptest.NewServer(gateway.Handler())
	defer server.Close()

	response, err := http.Post(server.URL+"/api/tasks", "application/json",
		strings.NewReader(`{"issue": "fix the parser", "repo_root": "/tmp/target"}`))
	if err != nil {
		t.Fatalf("create task failed: %v", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusCreated {
		t.Fatalf("expected 201, got %d", response.StatusCode)
	}
	var body map[string]any
	_ = json.NewDecoder(response.Body).Decode(&body)
	runID, ok := body["run_id"].(string)
	if !ok || runID == "" {
		t.Fatalf("missing run_id in response: %v", body)
	}
	if body["result"].(map[string]any)["outcome"] != "VERIFIED" {
		t.Fatalf("proxied result missing: %v", body)
	}

	// the recorded task is retrievable
	taskResponse, err := http.Get(server.URL + "/api/tasks/" + runID)
	if err != nil {
		t.Fatalf("task lookup failed: %v", err)
	}
	defer taskResponse.Body.Close()
	if taskResponse.StatusCode != http.StatusOK {
		t.Fatalf("expected 200 for recorded task, got %d", taskResponse.StatusCode)
	}
}

func TestCreateTaskRejectsEmptyIssue(t *testing.T) {
	gateway := NewGateway(LoadConfig(), nil)
	server := httptest.NewServer(gateway.Handler())
	defer server.Close()

	response, err := http.Post(server.URL+"/api/tasks", "application/json",
		strings.NewReader(`{"issue": ""}`))
	if err != nil {
		t.Fatalf("request failed: %v", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusBadRequest {
		t.Fatalf("expected 400 for empty issue, got %d", response.StatusCode)
	}
}

func TestUnknownTaskReturns404(t *testing.T) {
	gateway := NewGateway(LoadConfig(), nil)
	server := httptest.NewServer(gateway.Handler())
	defer server.Close()

	response, err := http.Get(server.URL + "/api/tasks/does-not-exist")
	if err != nil {
		t.Fatalf("request failed: %v", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusNotFound {
		t.Fatalf("expected 404, got %d", response.StatusCode)
	}
}

func TestProxyForwardsToOrchestrator(t *testing.T) {
	upstream := fakeOrchestrator(t, http.StatusOK, map[string]any{
		"agents": []string{"architect-1", "ver-1"},
	})
	defer upstream.Close()

	gateway := NewGateway(Config{OrchestratorURL: upstream.URL}, nil)
	server := httptest.NewServer(gateway.Handler())
	defer server.Close()

	response, err := http.Get(server.URL + "/api/agents")
	if err != nil {
		t.Fatalf("proxy request failed: %v", err)
	}
	defer response.Body.Close()
	var body map[string]any
	_ = json.NewDecoder(response.Body).Decode(&body)
	if body["agents"] == nil {
		t.Fatalf("expected proxied agents payload: %v", body)
	}
}

func TestHubBroadcastReachesClients(t *testing.T) {
	hub := NewHub()
	if hub.Count() != 0 {
		t.Fatal("hub must start empty")
	}
	hub.Broadcast([]byte(`{"event": "no-clients-attached"}`)) // must not block
	if hub.Count() != 0 {
		t.Fatal("broadcast without clients must be a no-op")
	}
}

func TestDashboardEndpoint(t *testing.T) {
	gateway := NewGateway(LoadConfig(), nil)
	server := httptest.NewServer(gateway.Handler())
	defer server.Close()

	response, err := http.Get(server.URL + "/")
	if err != nil {
		t.Fatalf("dashboard request failed: %v", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", response.StatusCode)
	}
}

func TestBroadcastEventEndpoint(t *testing.T) {
	gateway := NewGateway(LoadConfig(), nil)
	server := httptest.NewServer(gateway.Handler())
	defer server.Close()

	response, err := http.Post(server.URL+"/api/events", "application/json",
		strings.NewReader(`{"event": "test.event", "run_id": "r1"}`))
	if err != nil {
		t.Fatalf("broadcast request failed: %v", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", response.StatusCode)
	}
}
