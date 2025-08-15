package pipeline

import (
	"errors"
	"strings"

	"val/internal/adapters"
	"val/internal/output"
)

type Options struct {
	Mode       output.Mode
	Adapter    string
	TickersCSV string
}

func Run(opts Options) error {
	ad, ok := adapters.Get(opts.Adapter)
	if !ok {
		return errors.New("adapter not found: " + opts.Adapter)
	}
	tickers := splitCSV(opts.TickersCSV)
	raw, err := ad.Fetch(tickers)
	if err != nil {
		return err
	}
	var sink output.Sink
	switch opts.Mode {
	case output.ModeConsole:
		sink = output.NewConsoleSink()
	case output.ModeBroadcast:
		return errors.New("broadcast mode not yet implemented")
	case output.ModeGUI:
		return errors.New("gui mode not yet implemented")
	default:
		return errors.New("unknown mode")
	}
	return sink.Publish(raw)
}

func splitCSV(s string) []string {
	if s == "" {
		return nil
	}
	parts := strings.Split(s, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			out = append(out, p)
		}
	}
	return out
}
