package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"github.com/lsds/KungFu/srcs/go/cmd/kungfu-run/app"
	"net"
	"net/http"
	"os"
	"strconv"
	"time"
)

import "C"

type Message struct {
	Key string `json:"key"`
}

var httpc = http.Client{
	Transport: &http.Transport{
		DialContext: func(_ context.Context, _, _ string) (net.Conn, error) {
			return net.Dial("unix", "/tmp/http.sock")
		},
	},
}
var d = 0.0
var d1 = 0.0

//export GoKungfuRunMain
func GoKungfuRunMain() {
	args := os.Args[1:] // remove wrapper program name (`which python`)
	app.Main(args)
}

//export GoKungfuRunSendBegin
func GoKungfuRunSendBegin() {
	go goKungfuRunSendBegin()
}
func goKungfuRunSendBegin() {
	t0 := time.Now().UnixNano()
	contentType := "application/json;charset=utf-8"
	data := "begin:" + strconv.Itoa(GoKungfuRank())
	msg := Message{Key: data}
	b, err := json.Marshal(msg)
	if err != nil {
		return
	}
	body := bytes.NewBuffer(b)
	resp, err := httpc.Post("http://http.sock", contentType, body)
	if err != nil {
		return
	}
	defer resp.Body.Close()
	d = d + float64(time.Now().UnixNano()-t0)
}

//export GoKungfuRunSendEnd
func GoKungfuRunSendEnd() {
	go goKungfuRunSendEnd()
}
func goKungfuRunSendEnd() {
	t0 := time.Now().UnixNano()
	contentType := "application/json;charset=utf-8"
	data := "end:" + strconv.Itoa(GoKungfuRank())
	msg := Message{Key: data}
	b, err := json.Marshal(msg)
	if err != nil {
		return
	}
	body := bytes.NewBuffer(b)
	resp, err := httpc.Post("http://http.sock", contentType, body)
	if err != nil {
		return
	}
	defer resp.Body.Close()
	d1 = d1 + float64(time.Now().UnixNano()-t0)
}

//export GoKungfuRunSendTrainend
func GoKungfuRunSendTrainend() {
	contentType := "application/json;charset=utf-8"
	data := "trainend:" + strconv.Itoa(GoKungfuRank())
	msg := Message{Key: data}
	b, err := json.Marshal(msg)
	if err != nil {
		return
	}
	body := bytes.NewBuffer(b)
	resp, err := httpc.Post("http://http.sock", contentType, body)
	if err != nil {
		return
	}
	fmt.Println(d / 1e9)
	fmt.Println(d1 / 1e9)
	defer resp.Body.Close()
}
