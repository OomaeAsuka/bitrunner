# -*- coding: utf-8 -*-
# brwzrgame.py
import sys, time
import bitrunner as br

# System 設定情報
br.brInit()

while 1:
    # Where am I の取得
    wai = br.getWhereAmI()
    print(wai)

    psResult = dict(result=False)

    if wai["result"] == True:
        psResult = br.playStory(wai["story"])

    print(psResult)

    # Sleep
    time.sleep(br.sysvar_interval)
