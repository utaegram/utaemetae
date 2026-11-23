#!/bin/bash
# 천안 전체 주유소를 오피넷 aroundAll(반경 5km) 격자 조회로 수집
K=$(grep OPINET_KEY .env | cut -d= -f2 | tr -d '\r\n')
out=data/opinet_raw.txt; : > $out
for x in $(seq 298000 7000 345000); do for y in $(seq 445000 7000 495000); do
  for p in B027 D047 K015; do
    curl -s -m 20 "https://www.opinet.co.kr/api/aroundAll.do?code=$K&x=$x&y=$y&radius=5000&sort=1&prodcd=$p&out=json" | tr -d '\r\n\t' >> $out; echo >> $out
  done
done; done
