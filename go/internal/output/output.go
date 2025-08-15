package output

type Mode string

const (
	ModeConsole   Mode = "console"
	ModeBroadcast Mode = "broadcast"
	ModeGUI       Mode = "gui"
)

type Sink interface {
	Publish(items []map[string]any) error
}
