// Foreman Go TUI cockpit (platform P4, issue #73).
//
// Bubble Tea dashboard consuming the gateway: live engine events over
// WebSocket, run/event counters, q to quit, r to reconnect.
// Launch: `make tui-go` (GATEWAY_URL env, default ws://localhost:8080/ws).
package main

import (
	"fmt"
	"os"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/gorilla/websocket"
)

type eventMsg string        // one engine event from the WebSocket
type connectedMsg string    // dial succeeded
type reconnectMsg struct{}  // dial failed; user may press r

type model struct {
	gatewayURL string
	events     []string
	status     string
	connected  bool
	msgs       chan string
}

var (
	titleStyle   = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("212"))
	okStyle      = lipgloss.NewStyle().Foreground(lipgloss.Color("46")).Padding(0, 1)
	warnStyle    = lipgloss.NewStyle().Foreground(lipgloss.Color("196")).Padding(0, 1)
	eventStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("252"))
	borderStyle  = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).Padding(0, 1)
)

func (m model) Init() tea.Cmd {
	return tea.Batch(dial(m.gatewayURL, m.msgs), listen(m.msgs))
}

func dial(url string, msgs chan string) tea.Cmd {
	return func() tea.Msg {
		connection, _, err := websocket.DefaultDialer.Dial(url, nil)
		if err != nil {
			return reconnectMsg{}
		}
		go func() {
			defer connection.Close()
			for {
				_, payload, err := connection.ReadMessage()
				if err != nil {
					msgs <- "connection lost - press r to reconnect"
					return
				}
				msgs <- string(payload)
			}
		}()
		return connectedMsg(url)
	}
}

func listen(msgs chan string) tea.Cmd {
	return func() tea.Msg {
		return eventMsg(<-msgs)
	}
}

func (m model) Update(message tea.Msg) (tea.Model, tea.Cmd) {
	switch message := message.(type) {
	case tea.KeyMsg:
		switch message.String() {
		case "q", "ctrl+c":
			return m, tea.Quit
		case "r":
			m.status = "reconnecting..."
			return m, dial(m.gatewayURL, m.msgs)
		}
	case connectedMsg:
		m.connected = true
		m.status = "connected to " + string(message)
		return m, listen(m.msgs)
	case eventMsg:
		if string(message) == "connection lost - press r to reconnect" {
			m.connected = false
			m.status = string(message)
			return m, nil
		}
		m.events = append(m.events, fmt.Sprintf("%s  %s",
			time.Now().Format("15:04:05"), string(message)))
		return m, listen(m.msgs)
	case reconnectMsg:
		m.connected = false
		m.status = "disconnected - press r to reconnect"
	}
	return m, nil
}

func (m model) View() string {
	style := okStyle
	if !m.connected {
		style = warnStyle
	}
	header := titleStyle.Render("Foreman Go TUI") + "  " +
		style.Render(fmt.Sprintf("%s  events: %d", m.status, len(m.events)))
	var body strings.Builder
	body.WriteString(header + "\n\n")
	start := 0
	if len(m.events) > 20 {
		start = len(m.events) - 20
	}
	for _, event := range m.events[start:] {
		body.WriteString(eventStyle.Render("  "+event) + "\n")
	}
	if len(m.events) == 0 {
		body.WriteString("  waiting for engine events...\n")
	}
	body.WriteString("\n  [q] quit  [r] reconnect")
	return borderStyle.Render(body.String())
}

func main() {
	gatewayURL := os.Getenv("GATEWAY_URL")
	if gatewayURL == "" {
		gatewayURL = "ws://localhost:8080/ws"
	}
	if _, err := tea.NewProgram(
		model{gatewayURL: gatewayURL, msgs: make(chan string, 64)},
	).Run(); err != nil {
		fmt.Fprintln(os.Stderr, "tui error:", err)
		os.Exit(1)
	}
}
