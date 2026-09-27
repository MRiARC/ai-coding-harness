// Foreman Go TUI cockpit (platform P4, issue #73).
//
// Bubble Tea dashboard consuming the gateway: live engine events over
// WebSocket, interactive task launcher, plan/activity/verification tabs,
// token meter, and agent status.
// Launch: `make tui-go` (GATEWAY_URL env, default ws://localhost:8080/ws).
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/gorilla/websocket"
)

type eventMsg string
type connectedMsg string
type reconnectMsg struct{}
type taskSubmitResultMsg struct {
	runID string
	err   error
}

type Tab int

const (
	TabActivity Tab = iota
	TabPlan
	TabVerification
	TabTokens
	TabAgents
)

type Subtask struct {
	ID       string
	Agent    string
	Status   string // PENDING, RUNNING, DONE, FAILED
	Summary  string
}

type StageStatus struct {
	Name   string
	Passed bool
	Detail string
}

type EventEntry struct {
	Time    string
	Kind    string
	RunID   string
	Summary string
	Success *bool
}

type model struct {
	gatewayURL   string
	apiURL       string
	connected    bool
	status       string
	activeTab    Tab
	activeRunID  string
	totalTokens  int
	events       []EventEntry
	plan         []Subtask
	stages       map[string]StageStatus
	agentStatus  map[string]string // agentId -> status
	msgs         chan string

	// New task prompt mode
	inNewTaskMode bool
	inputField    int // 0: issue, 1: repoRoot
	issueInput    string
	repoInput     string
	submitNotice  string
}

var (
	titleStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("#ffffff")).
			Background(lipgloss.Color("#2563eb")).
			Padding(0, 1)

	headerStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("#3b82f6")).
			Padding(0, 1).
			MarginBottom(1)

	activeTabStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("#ffffff")).
			Background(lipgloss.Color("#3b82f6")).
			Padding(0, 2)

	inactiveTabStyle = lipgloss.NewStyle().
				Foreground(lipgloss.Color("#94a3b8")).
				Background(lipgloss.Color("#1e293b")).
				Padding(0, 2)

	borderStyle = lipgloss.NewStyle().Border(lipgloss.RoundedBorder()).Padding(0, 1)

	contentBoxStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(lipgloss.Color("#334155")).
			Padding(1, 2).
			Height(14)

	footerStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("#64748b")).
			MarginTop(1)

	okStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("#10b981")).Bold(true)
	warnStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#f59e0b")).Bold(true)
	errStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("#ef4444")).Bold(true)
	dimStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("#64748b"))
	cyanStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#38bdf8"))
)

func initialModel(gatewayURL string) model {
	apiURL := "http://localhost:8080"
	if strings.HasPrefix(gatewayURL, "ws://") {
		apiURL = "http://" + strings.TrimPrefix(gatewayURL, "ws://")
		if idx := strings.Index(apiURL, "/"); idx != -1 {
			apiURL = apiURL[:idx]
		}
	} else if strings.HasPrefix(gatewayURL, "wss://") {
		apiURL = "https://" + strings.TrimPrefix(gatewayURL, "wss://")
		if idx := strings.Index(apiURL, "/"); idx != -1 {
			apiURL = apiURL[:idx]
		}
	}

	return model{
		gatewayURL:   gatewayURL,
		apiURL:       apiURL,
		status:       "connecting...",
		msgs:         make(chan string, 128),
		stages:       make(map[string]StageStatus),
		agentStatus:  map[string]string{"architect": "Ready", "manager": "Ready", "sde-1": "Ready", "verifier": "Ready"},
		activeRunID:  "—",
		repoInput:    "fixtures/mini-repo",
	}
}

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

func submitTask(apiURL, issue, repoRoot string) tea.Cmd {
	return func() tea.Msg {
		body, _ := json.Marshal(map[string]string{
			"issue":     issue,
			"repo_root": repoRoot,
		})
		resp, err := http.Post(apiURL+"/api/tasks", "application/json", bytes.NewReader(body))
		if err != nil {
			return taskSubmitResultMsg{err: err}
		}
		defer resp.Body.Close()
		var res map[string]any
		_ = json.NewDecoder(resp.Body).Decode(&res)
		runID, _ := res["run_id"].(string)
		return taskSubmitResultMsg{runID: runID}
	}
}

func (m model) Update(message tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := message.(type) {
	case tea.KeyMsg:
		if m.inNewTaskMode {
			switch msg.String() {
			case "esc":
				m.inNewTaskMode = false
				m.submitNotice = "Cancelled task entry"
				return m, nil
			case "tab":
				m.inputField = (m.inputField + 1) % 2
				return m, nil
			case "enter":
				if strings.TrimSpace(m.issueInput) == "" {
					m.submitNotice = "Please enter an issue description"
					return m, nil
				}
				m.inNewTaskMode = false
				m.submitNotice = fmt.Sprintf("Launching run for: %s...", m.issueInput)
				return m, submitTask(m.apiURL, m.issueInput, m.repoInput)
			case "backspace":
				if m.inputField == 0 && len(m.issueInput) > 0 {
					m.issueInput = m.issueInput[:len(m.issueInput)-1]
				} else if m.inputField == 1 && len(m.repoInput) > 0 {
					m.repoInput = m.repoInput[:len(m.repoInput)-1]
				}
				return m, nil
			default:
				if len(msg.String()) == 1 {
					if m.inputField == 0 {
						m.issueInput += msg.String()
					} else {
						m.repoInput += msg.String()
					}
				}
				return m, nil
			}
		}

		// Normal Mode Keybindings
		switch msg.String() {
		case "q", "ctrl+c":
			return m, tea.Quit
		case "r":
			m.status = "reconnecting..."
			return m, dial(m.gatewayURL, m.msgs)
		case "n":
			m.inNewTaskMode = true
			m.inputField = 0
			m.submitNotice = ""
			return m, nil
		case "tab":
			m.activeTab = (m.activeTab + 1) % 5
			return m, nil
		case "shift+tab":
			m.activeTab = (m.activeTab + 4) % 5
			return m, nil
		case "1":
			m.activeTab = TabActivity
		case "2":
			m.activeTab = TabPlan
		case "3":
			m.activeTab = TabVerification
		case "4":
			m.activeTab = TabTokens
		case "5":
			m.activeTab = TabAgents
		}

	case connectedMsg:
		m.connected = true
		m.status = "connected"
		return m, listen(m.msgs)

	case reconnectMsg:
		m.connected = false
		m.status = "disconnected - press r to reconnect"

	case taskSubmitResultMsg:
		if msg.err != nil {
			m.submitNotice = fmt.Sprintf("Error launching task: %v", msg.err)
		} else {
			m.submitNotice = fmt.Sprintf("Task started! Run ID: %s", msg.runID)
			m.activeRunID = msg.runID
		}

	case eventMsg:
		raw := string(msg)
		if raw == "connection lost - press r to reconnect" {
			m.connected = false
			m.status = raw
			return m, nil
		}
		m.parseEvent(raw)
		return m, listen(m.msgs)
	}

	return m, nil
}

func (m *model) parseEvent(raw string) {
	var ev map[string]any
	if err := json.Unmarshal([]byte(raw), &ev); err != nil {
		m.events = append(m.events, EventEntry{
			Time:    time.Now().Format("15:04:05"),
			Kind:    "raw",
			Summary: raw,
		})
		return
	}

	kind, _ := ev["event"].(string)
	if kind == "" {
		kind = "unknown"
	}
	runID, _ := ev["run_id"].(string)
	if runID != "" {
		m.activeRunID = runID
	}

	summary := ""
	var success *bool
	if s, ok := ev["success"].(bool); ok {
		success = &s
	}

	// Update components by event kind
	switch kind {
	case "run.start":
		if issue, ok := ev["issue"].(string); ok {
			summary = fmt.Sprintf("Run started: %s", issue)
		} else {
			summary = "Run started"
		}
		m.agentStatus["architect"] = "Planning"

	case "specialist.assigned":
		task, _ := ev["task"].(string)
		agent, _ := ev["agent"].(string)
		summary = fmt.Sprintf("Task '%s' assigned to agent '%s'", task, agent)
		m.agentStatus["manager"] = "Assigning"
		m.agentStatus[agent] = "Active"
		m.plan = append(m.plan, Subtask{
			ID:     task,
			Agent:  agent,
			Status: "RUNNING",
		})

	case "specialist.result":
		task, _ := ev["task"].(string)
		taskSum, _ := ev["summary"].(string)
		summary = fmt.Sprintf("Task '%s' completed: %s", task, taskSum)
		for i, sub := range m.plan {
			if sub.ID == task {
				if success != nil && *success {
					m.plan[i].Status = "DONE"
				} else {
					m.plan[i].Status = "FAILED"
				}
				m.plan[i].Summary = taskSum
			}
		}

	case "verification.stage":
		stage, _ := ev["stage"].(string)
		detail, _ := ev["detail"].(string)
		passed, _ := ev["passed"].(bool)
		m.stages[stage] = StageStatus{
			Name:   stage,
			Passed: passed,
			Detail: detail,
		}
		summary = fmt.Sprintf("Verification stage '%s': passed=%v (%s)", stage, passed, detail)
		m.agentStatus["verifier"] = "Verifying"

	case "run.end", "task.completed":
		summary = "Run completed"
		m.agentStatus["architect"] = "Ready"
		m.agentStatus["manager"] = "Ready"
		m.agentStatus["verifier"] = "Done"

	default:
		summary = fmt.Sprintf("%v", raw)
	}

	// Token usage
	if usage, ok := ev["usage"].(map[string]any); ok {
		if tok, ok := usage["total_tokens"].(float64); ok {
			m.totalTokens += int(tok)
		}
	}

	m.events = append(m.events, EventEntry{
		Time:    time.Now().Format("15:04:05"),
		Kind:    kind,
		RunID:   runID,
		Summary: summary,
		Success: success,
	})
}

func (m model) View() string {
	var b strings.Builder

	// Header Bar
	statusPill := okStyle.Render("● CONNECTED")
	if !m.connected {
		statusPill = warnStyle.Render("○ " + m.status)
	}

	header := fmt.Sprintf("%s  %s  Run: %s  Tokens: %s  Events: %d",
		titleStyle.Render("⚡ FOREMAN COCKPIT"),
		statusPill,
		cyanStyle.Render(m.activeRunID),
		warnStyle.Render(fmt.Sprintf("%d", m.totalTokens)),
		len(m.events),
	)
	b.WriteString(headerStyle.Render(header) + "\n")

	// Notice Banner
	if m.submitNotice != "" {
		b.WriteString(warnStyle.Render("  ℹ " + m.submitNotice) + "\n\n")
	}

	// Modal: New Task
	if m.inNewTaskMode {
		b.WriteString(m.renderNewTaskModal())
		return borderStyle.Render(b.String())
	}

	// Tab bar
	b.WriteString(m.renderTabBar() + "\n")

	// Main Tab Content
	switch m.activeTab {
	case TabActivity:
		b.WriteString(contentBoxStyle.Render(m.renderActivityView()))
	case TabPlan:
		b.WriteString(contentBoxStyle.Render(m.renderPlanView()))
	case TabVerification:
		b.WriteString(contentBoxStyle.Render(m.renderVerificationView()))
	case TabTokens:
		b.WriteString(contentBoxStyle.Render(m.renderTokensView()))
	case TabAgents:
		b.WriteString(contentBoxStyle.Render(m.renderAgentsView()))
	}

	// Footer
	b.WriteString("\n" + footerStyle.Render(
		"[n] New Task   [tab/1-5] Switch Tab   [r] Reconnect   [q] Quit",
	))

	return borderStyle.Render(b.String())
}

func (m model) renderTabBar() string {
	tabs := []string{
		fmt.Sprintf("1 Activity (%d)", len(m.events)),
		fmt.Sprintf("2 Plan (%d)", len(m.plan)),
		"3 Verification",
		"4 Tokens",
		"5 Agents",
	}

	var rendered []string
	for i, t := range tabs {
		if Tab(i) == m.activeTab {
			rendered = append(rendered, activeTabStyle.Render(t))
		} else {
			rendered = append(rendered, inactiveTabStyle.Render(t))
		}
	}
	return strings.Join(rendered, " ")
}

func (m model) renderActivityView() string {
	if len(m.events) == 0 {
		return dimStyle.Render("No events received yet. Press [n] to start a task or wait for engine stream...")
	}
	var lines []string
	start := 0
	if len(m.events) > 15 {
		start = len(m.events) - 15
	}
	for _, ev := range m.events[start:] {
		tag := cyanStyle.Render(fmt.Sprintf("[%s]", ev.Kind))
		status := ""
		if ev.Success != nil {
			if *ev.Success {
				status = okStyle.Render("✓ OK")
			} else {
				status = errStyle.Render("✗ FAIL")
			}
		}
		lines = append(lines, fmt.Sprintf("%s %s %s %s",
			dimStyle.Render(ev.Time), tag, status, ev.Summary))
	}
	return strings.Join(lines, "\n")
}

func (m model) renderPlanView() string {
	if len(m.plan) == 0 {
		return dimStyle.Render("No active plan. When a task is launched, the Architect's subtasks appear here.")
	}
	var lines []string
	lines = append(lines, titleStyle.Render("SUBTASK PIPELINE"))
	for _, sub := range m.plan {
		st := dimStyle.Render("[PENDING]")
		if sub.Status == "RUNNING" {
			st = cyanStyle.Render("[RUNNING]")
		} else if sub.Status == "DONE" {
			st = okStyle.Render("[DONE]")
		} else if sub.Status == "FAILED" {
			st = errStyle.Render("[FAILED]")
		}
		lines = append(lines, fmt.Sprintf("  %s %s (assigned: %s) — %s",
			st, sub.ID, sub.Agent, sub.Summary))
	}
	return strings.Join(lines, "\n")
}

func (m model) renderVerificationView() string {
	if len(m.stages) == 0 {
		return dimStyle.Render("No verification run yet. The 5 verification stages will display live verdicts here.")
	}
	var lines []string
	lines = append(lines, titleStyle.Render("5-STAGE VERIFICATION PIPELINE"))
	for _, name := range []string{"integrity", "syntax", "tests", "smells", "regression"} {
		st, ok := m.stages[name]
		if !ok {
			lines = append(lines, fmt.Sprintf("  %s %s: not evaluated", dimStyle.Render("○"), name))
		} else if st.Passed {
			lines = append(lines, fmt.Sprintf("  %s %s: %s", okStyle.Render("✓ PASS"), name, st.Detail))
		} else {
			lines = append(lines, fmt.Sprintf("  %s %s: %s", errStyle.Render("✗ FAIL"), name, st.Detail))
		}
	}
	return strings.Join(lines, "\n")
}

func (m model) renderTokensView() string {
	var lines []string
	lines = append(lines, titleStyle.Render("TOKEN BUDGET & SPEND"))
	lines = append(lines, fmt.Sprintf("  Total Tokens Consumed: %s", warnStyle.Render(fmt.Sprintf("%d", m.totalTokens))))
	lines = append(lines, fmt.Sprintf("  Current Run ID:        %s", cyanStyle.Render(m.activeRunID)))
	lines = append(lines, fmt.Sprintf("  Total Events Streamed: %d", len(m.events)))
	lines = append(lines, fmt.Sprintf("  Estimated Cost ($):    $%0.4f", float64(m.totalTokens)*0.000003))
	return strings.Join(lines, "\n")
}

func (m model) renderAgentsView() string {
	var lines []string
	lines = append(lines, titleStyle.Render("AGENT ROSTER & STATUS"))
	for agent, st := range m.agentStatus {
		badge := dimStyle.Render(st)
		if st == "Active" || st == "Planning" || st == "Verifying" {
			badge = cyanStyle.Render(st)
		} else if st == "Done" {
			badge = okStyle.Render(st)
		}
		lines = append(lines, fmt.Sprintf("  🤖 %-12s : %s", agent, badge))
	}
	return strings.Join(lines, "\n")
}

func (m model) renderNewTaskModal() string {
	var b strings.Builder
	b.WriteString(titleStyle.Render("🚀 LAUNCH NEW TASK") + "\n\n")

	cursor0 := "  "
	cursor1 := "  "
	if m.inputField == 0 {
		cursor0 = cyanStyle.Render("> ")
	} else {
		cursor1 = cyanStyle.Render("> ")
	}

	b.WriteString(fmt.Sprintf("%sIssue Description: %s_\n", cursor0, m.issueInput))
	b.WriteString(fmt.Sprintf("%sTarget Repo Path:  %s_\n\n", cursor1, m.repoInput))

	b.WriteString(dimStyle.Render("[tab] Switch field   [enter] Submit Task   [esc] Cancel\n"))
	return contentBoxStyle.Render(b.String())
}

func main() {
	gatewayURL := os.Getenv("GATEWAY_URL")
	if gatewayURL == "" {
		gatewayURL = "ws://localhost:8080/ws"
	}
	m := initialModel(gatewayURL)
	if _, err := tea.NewProgram(m).Run(); err != nil {
		fmt.Fprintln(os.Stderr, "tui error:", err)
		os.Exit(1)
	}
}
