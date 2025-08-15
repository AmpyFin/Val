package adapters

import "math"

type mock struct{}

func (m *mock) Name() string { return "mock" }

func (m *mock) Fields() []string {
	return []string{"ticker", "price", "eps_ttm", "growth_5y_est"}
}

func (m *mock) Fetch(tickers []string) ([]map[string]any, error) {
	out := make([]map[string]any, 0, len(tickers))
	for _, t := range tickers {
		base := float64(len(t)*7 + 15)
		eps := base/10.0 + 0.8
		growth := 0.12
		price := base * 1.7
		out = append(out, map[string]any{
			"ticker":        t,
			"price":         round(price, 2),
			"eps_ttm":       round(eps, 3),
			"growth_5y_est": round(growth, 3),
		})
	}
	return out, nil
}

func round(v float64, p int) float64 {
	f := math.Pow(10, float64(p))
	return math.Round(v*f) / f
}

func init() {
	Register(&mock{})
}
