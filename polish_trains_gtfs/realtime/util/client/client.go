// SPDX-FileCopyrightText: 2026 Mikołaj Kuranowski
// SPDX-License-Identifier: MIT

package client

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"math/rand/v2"
	"net/http"
	"net/url"
	"os"
	"time"

	"github.com/MKuranowski/PolishTrainsGTFS/polish_trains_gtfs/realtime/util/http2"
	"github.com/MKuranowski/PolishTrainsGTFS/polish_trains_gtfs/realtime/util/vpn"
)

const PoolClientBackoff = 30 * time.Minute

type JSONDuration time.Duration

func (d JSONDuration) String() string {
	return time.Duration(d).String()
}

func (d JSONDuration) MarshalText() (text []byte, err error) {
	return []byte(time.Duration(d).String()), nil
}

func (d *JSONDuration) UnmarshalText(text []byte) error {
	duration, err := time.ParseDuration(string(text))
	*d = JSONDuration(duration)
	return err
}

type ClientConfig struct {
	Key       string               `json:"key"`
	RateLimit JSONDuration         `json:"rate_limit,omitempty"`
	Proxy     *url.URL             `json:"proxy,omitempty"`
	Wireguard *vpn.WireguardConfig `json:"wireguard,omitempty"`
}

func (c ClientConfig) Instantiate() *Client {
	client := new(Client)
	client.Key = c.Key
	client.RateLimit = time.Duration(c.RateLimit)

	if c.Wireguard != nil && c.Proxy != nil {
		panic("Client can't use Wireguard VPN and a proxy at the same time")
	} else if c.Wireguard != nil {
		var err error
		client.Doer, client.Closer, err = vpn.NewWireguardClient(c.Wireguard)
		if err != nil {
			panic(fmt.Errorf("failed to connect to vpn: %w", err))
		}
	} else if c.Proxy != nil {
		transport := http.DefaultTransport.(*http.Transport).Clone()
		transport.Proxy = http.ProxyURL(c.Proxy)
		client.Doer = &http.Client{Transport: transport}
	} else {
		client.Doer = http.DefaultClient
	}

	return client
}

type Client struct {
	Key       string
	Closer    func()
	Doer      http2.Doer
	RateLimit time.Duration
	nextRun   time.Time
}

func (c *Client) Do(req *http.Request) (*http.Response, error) {
	if c.RateLimit != 0 {
		sleep := time.Until(c.nextRun)
		if sleep > 0 {
			time.Sleep(sleep)
		}
		c.nextRun = time.Now().Add(c.RateLimit)
	}

	return c.Doer.Do(req)
}

func (c *Client) Close() {
	if c.Closer != nil {
		c.Closer()
	}
}

type Pool struct {
	clients []*Client
	backoff []time.Time
	last    int
}

func NewPool(clients ...*Client) *Pool {
	if len(clients) == 0 {
		panic("client.NewPool: no clients provided")
	}

	return &Pool{
		clients: clients,
		backoff: make([]time.Time, len(clients)),
	}
}

func NewPoolFromConfigs(configs ...ClientConfig) *Pool {
	clients := make([]*Client, len(configs))
	for i, config := range configs {
		clients[i] = config.Instantiate()
	}
	return NewPool(clients...)
}

func NewPoolFromJSON(path string) (*Pool, error) {
	content, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	var configs []ClientConfig
	err = json.Unmarshal(content, &configs)
	if err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}

	return NewPoolFromConfigs(configs...), nil
}

func (p *Pool) Close() {
	for _, c := range p.clients {
		c.Close()
	}
}

func (p *Pool) Select() *Client {
	// Short-circuit when there's only one client
	if len(p.clients) <= 1 {
		return p.clients[0]
	}

	// Try a couple of times to select a non-backoffed client
	now := time.Now()
	for try := 0; try < len(p.clients); try++ {
		idx := rand.IntN(len(p.clients))
		if now.After(p.backoff[idx]) {
			p.last = idx
			return p.clients[idx]
		}
	}

	// Failed to do so - pick a random one
	slog.Warn("Failed to select a non-backoffed client for the request")
	idx := rand.IntN(len(p.clients))
	p.last = idx
	return p.clients[idx]
}

func (p *Pool) BackoffLast() {
	p.backoff[p.last] = time.Now().Add(PoolClientBackoff)
}
