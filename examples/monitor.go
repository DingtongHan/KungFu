package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"net"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

type server int

var trainend []int
var times []int64

type Message struct {
	Key string `json:"key"`
}

func (h *server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	var msg Message
	err := json.NewDecoder(r.Body).Decode(&msg)
	if err != nil {
		return
	}
	datas := strings.Split(string(msg.Key), ":")
	intva, err := strconv.Atoi(datas[1])
	if err != nil {
	}
	if datas[0] == "trainend" {
		trainend[intva] = 1
	}
	if datas[0] == "begin" {
		times[intva] = time.Now().Unix()
	}
	if datas[0] == "end" {
		times[intva] = 0
	}
}
func main() {
	var s server
	epoch := flag.Int("epoch", 0, "epoch")
	flag.Parse()
	for i := 0; i < *epoch; i++ {
		trainend = append(trainend, 0)
		times = append(times, 0)
	}
	_, err := os.Stat("/tmp/http.sock")
	if err != nil && os.IsNotExist(err) {
	} else {
		err1 := os.Remove("/tmp/http.sock")
		if err1 != nil {
			panic("Cannot delete: " + err.Error())
		}
	}

	addr, err := net.ResolveUnixAddr("unix", "/tmp/http.sock")
	if err != nil {
		panic("Cannot resolve unix addr: " + err.Error())
	}
	listener, err := net.ListenUnix("unix", addr)
	if err != nil {
		panic("Cannot resolve unix addr: " + err.Error())
	}
	var wg sync.WaitGroup
	wg.Add(2)
	go func(s server) {
		http.Serve(listener, &s)
		wg.Done()
	}(s)
	go func() {
		for {
			trainendflag := 0
			for i := 0; i < *epoch; i++ {
				if trainend[i] == 1 {
					trainendflag = trainendflag + 1
				}
				if a := time.Now().Unix() - times[i]; a > 10 {
					if times[i] != 0 {
						flag := "some machine died"
						fmt.Println(flag)
						os.Exit(0)
					}
				}
			}
			if trainendflag == *epoch {
				fmt.Println("train end")
				os.Exit(0)
			}
		}
		wg.Done()
	}()
	wg.Wait()
}
