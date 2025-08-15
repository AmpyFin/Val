package pipeline

import (
	"errors"
	"strings"

	"val/internal/adapters"
	"val/internal/output"
	"val/internal/strategies"
)

type Options struct {
	Mode       output.Mode
	Adapter    string
	Strategy   string
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

	evals, err := strategies.Eval(opts.Strategy, raw)
	if err != nil {
		return err
	}

	fairByTicker := map[string]strategies.EvalResult{}
	for _, e := range evals {
		fairByTicker[e.Ticker] = e
	}

	final := make([]map[string]any, 0, len(raw))
	for _, r := range raw {
		t, _ := r["ticker"].(string)
		price, _ := r["price"].(float64)
		ev, ok := fairByTicker[t]
		if !ok {
			continue
		}
		fv := ev.FairValue
		mos := 0.0
		if fv > 0 {
			mos = (fv - price) / fv
		}
		row := map[string]any{
			"ticker":      t,
			"price":       price,
			"fair_value":  fv,
			"mos":         mos,
			"strategy":    opts.Strategy,
			"notes":       ev.Notes,
			"conf":        ev.Conf,
		}
		final = append(final, row)
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
	return sink.Publish(final)
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
