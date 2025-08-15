package main

import (
	"flag"
	"log"

	"val/internal/output"
	"val/internal/pipeline"
	_ "val/internal/adapters"
)

func main() {
	mode := flag.String("mode", "console", "one of: console|broadcast|gui")
	adapter := flag.String("adapter", "mock", "adapter name")
	tickers := flag.String("tickers", "AAPL,MSFT,NVDA", "comma-separated tickers")
	flag.Parse()

	opts := pipeline.Options{
		Mode:       output.Mode(*mode),
		Adapter:    *adapter,
		TickersCSV: *tickers,
	}
	if err := pipeline.Run(opts); err != nil {
		log.Fatal(err)
	}
}
