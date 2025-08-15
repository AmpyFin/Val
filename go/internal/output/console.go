package output

import (
	"fmt"
	"sort"
)

type ConsoleSink struct{}

func NewConsoleSink() *ConsoleSink { return &ConsoleSink{} }

func (c *ConsoleSink) Publish(items []map[string]any) error {
	if len(items) == 0 {
		fmt.Println("no results")
		return nil
	}
	cols := make([]string, 0)
	seen := map[string]bool{}
	for _, it := range items {
		for k := range it {
			if !seen[k] {
				seen[k] = true
				cols = append(cols, k)
			}
		}
	}
	sort.Strings(cols)
	fmt.Println("----- VAL RESULTS (console mode) -----")
	fmt.Println(cols)
	for _, it := range items {
		row := make([]any, len(cols))
		for i, k := range cols {
			row[i] = it[k]
		}
		fmt.Println(row...)
	}
	return nil
}
