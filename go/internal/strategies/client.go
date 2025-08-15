package strategies

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"
)

type evalItem struct {
	Ticker string                 `json:"ticker"`
	Data   map[string]any         `json:"data"`
}
type evalRequest struct {
	Strategy string     `json:"strategy"`
	Items    []evalItem `json:"items"`
}

type resultModel struct {
	FairValue float64                `json:"fair_value"`
	Inputs    map[string]any         `json:"inputs"`
	Notes     string                 `json:"notes"`
	Conf      float64                `json:"conf"`
}
type evalItemResp struct {
	Ticker string      `json:"ticker"`
	Result resultModel `json:"result"`
}
type evalResponse struct {
	Items []evalItemResp `json:"items"`
}

type EvalResult struct {
	Ticker    string
	FairValue float64
	Inputs    map[string]any
	Notes     string
	Conf      float64
}

func Eval(strategy string, rows []map[string]any) ([]EvalResult, error) {
	baseURL := os.Getenv("STRAT_URL")
	if baseURL == "" {
		baseURL = "http://localhost:8000"
	}
	url := baseURL + "/eval"

	items := make([]evalItem, 0, len(rows))
	for _, r := range rows {
		t, _ := r["ticker"].(string)
		if t == "" {
			continue
		}
		data := map[string]any{}
		for k, v := range r {
			if k == "ticker" {
				continue
			}
			data[k] = v
		}
		items = append(items, evalItem{Ticker: t, Data: data})
	}

	req := evalRequest{Strategy: strategy, Items: items}
	body, err := json.Marshal(req)
	if err != nil {
		return nil, err
	}

	httpClient := &http.Client{Timeout: 10 * time.Second}
	resp, err := httpClient.Post(url, "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		var m map[string]any
		_ = json.NewDecoder(resp.Body).Decode(&m)
		return nil, fmt.Errorf("strategy service error %d: %v", resp.StatusCode, m)
	}

	var out evalResponse
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, err
	}

	results := make([]EvalResult, 0, len(out.Items))
	for _, it := range out.Items {
		results = append(results, EvalResult{
			Ticker:    it.Ticker,
			FairValue: it.Result.FairValue,
			Inputs:    it.Result.Inputs,
			Notes:     it.Result.Notes,
			Conf:      it.Result.Conf,
		})
	}
	return results, nil
}
