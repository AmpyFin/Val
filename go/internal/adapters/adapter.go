package adapters

type Adapter interface {
	Name() string
	Fields() []string
	Fetch(tickers []string) ([]map[string]any, error)
}

var registry = map[string]Adapter{}

func Register(a Adapter) { registry[a.Name()] = a }

func Get(name string) (Adapter, bool) { a, ok := registry[name]; return a, ok }

func Names() []string {
	out := make([]string, 0, len(registry))
	for k := range registry {
		out = append(out, k)
	}
	return out
}
