#-*- coding: utf-8 -*-
import toml
import numpy as np
import imutils
import imutils_convenience as imc
import sys
import os
import argparse
import pyautogui
import time
import cv2
import re # Use this for Regular Expressions
import requests  # Use this for Slack
import threading
import datetime
from PIL import Image

# System parameter
sysvar_args = None
sysvar_scriptdir = "Scenarios"
sysvar_imgdir = sysvar_scriptdir + "/default" 
sysvar_script = "script.toml"
sysvar_snippet_script = "script-snippet.toml"
sysvar_ratina = True
sysvar_timeout = 10
sysvar_savess = "ss.png"
sysvar_saveseq = False
sysvar_interval = 10
sysvar_delay = 0.0
sysvar_threshold = 0.9
sysvar_searchzoom = [1.0, 0.90, 0.75, 0.67, 0.50, 0.33, 0.25]
sysvar_slacktoken = ""
sysvar_slackchannel = ""
sysvar_slackthumbssize = 600
sysvar_top = 0
sysvar_left = 0
sysvar_bottom = 0
sysvar_right = 0
sysvar_runafter = dict()

# BitRunner iniitial method
def brInit ():

    # Parse command line argument
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--reduction-template", action="store_true", help="Reduction template image to 1/2")
    parser.add_argument("-r", "--ratina-off", action="store_true", help="Ratina display")
    parser.add_argument("-s", "--showscript", action="store_true", help="Show read script")
    parser.add_argument("-g", "--show-recresult", action="store_true", help="Show recognized result")
    parser.add_argument("-d", "--debug", action="store_true", help="Debug mode")
    parser.add_argument("-c", "--script-path", help="Script path name")

    global sysvar_args
    sysvar_args = parser.parse_args()
    print(">>> Parsed command line argments.")
    print("    " + str(sysvar_args))

    # Set specific toml file, image directory
    global sysvar_script, sysvar_snippet_script, sysvar_imgdir
    if sysvar_args.script_path != None:
        sysvar_script = sysvar_scriptdir + "/" + sysvar_args.script_path + "/" + sysvar_script
        sysvar_snippet_script = sysvar_scriptdir + "/" + sysvar_args.script_path + "/" + sysvar_snippet_script
        sysvar_imgdir = sysvar_scriptdir + "/" + sysvar_args.script_path
    else:
        sysvar_script = sysvar_scriptdir + "/" + sysvar_script
        sysvar_snippet_script = sysvar_scriptdir + "/" + sysvar_snippet_script

    # Read system parameter by sysvar_script
    script = readSystemFromScript()
    if sysvar_args.showscript == True: print(script)

    # Read system parameter
    global sysvar_ratina
    sysvar_ratina = (True if script["ratina"] == 1 else False) if "ratina" in script and isinstance(script["ratina"], int) else sysvar_ratina
    sysvar_ratina = False if sysvar_args.ratina_off == True else sysvar_ratina

    # global sysvar_reductiontemplate
    # sysvar_reductiontemplate = sysvar_reductiontemplate if sysvar_args.reductiontemplate == None else bool(sysvar_args.reductiontemplate)
    # print(sysvar_reductiontemplate)

    global sysvar_timeout
    sysvar_timeout = script["timeout"] if "timeout" in script and isinstance(script["timeout"], int) else sysvar_timeout

    global sysvar_savess

    global sysvar_saveseq
    sysvar_saveseq = (True if script["saveimagesequence"] == 1 else False) if "saveimagesequence" in script and isinstance(script["saveimagesequence"], int) else sysvar_saveseq

    global sysvar_interval
    sysvar_interval = script["interval"] if "interval" in script and isinstance(script["interval"], int) else sysvar_interval

    global sysvar_delay
    sysvar_delay = script["delay"] if "delay" in script and isinstance(script["delay"], float) else sysvar_delay

    global sysvar_threshold
    sysvar_threshold = script["threshold"] if "threshold" in script and isinstance(script["threshold"], float) else sysvar_threshold

    global sysvar_searchzoom
    sysvar_searchzoom = script["searchzoom"] if "searchzoom" in script and isinstance(script["searchzoom"], list) else sysvar_searchzoom

    global sysvar_slacktoken
    sysvar_slacktoken = script["slacktoken"] if "slacktoken" in script and isinstance(script["slacktoken"], str) else sysvar_slacktoken

    global sysvar_slackchannel
    sysvar_slackchannel = script["slackchannel"] if "slackchannel" in script and isinstance(script["slackchannel"], str) else sysvar_slackchannel

    topLeft = script["recttopleft"] if "recttopleft" in script and isinstance(script["recttopleft"], str) else ""
    bottomRight = script["rectbottomright"] if "rectbottomright" in script and isinstance(script["rectbottomright"], str) else ""
    getTargetRect(topLeft, bottomRight)

    return dict(result=True)

# Get Capture Rect
def getTargetRect (topLeft, bottomRight):

    global sysvar_top, sysvar_left, sysvar_bottom, sysvar_right

    resTopLeft = findTarget(topLeft, sysvar_savess, sysvar_threshold)
    resBottomRight = findTarget(bottomRight, sysvar_savess, sysvar_threshold)

    if resTopLeft["result"] == True and resBottomRight["result"] == True:
        sysvar_top = resTopLeft["top"]
        sysvar_left = resTopLeft["left"]
        sysvar_bottom = resBottomRight["top"] + resBottomRight["width"]
        sysvar_right = resBottomRight["left"] + resBottomRight["height"]
        print(">>> Target Rect: ({0}, {1}) ({2}, {3})".format(sysvar_top, sysvar_left, sysvar_bottom, sysvar_right))
        return dict(result=True)
    else:
        return dict(result=False)

# Read Script
def readScript (scriptName, sectionName=None):

    print(">>> Reading script" + (": " if sectionName == None else " for " + sectionName + ": ") + scriptName)
    try:
        if sys.version_info >= (3, 0, 0):
            with open(scriptName, encoding="utf_8") as scriptfile:
                data = scriptfile.read()
                script = toml.loads(data)
        else:
            with open(scriptName) as scriptfile:
                data = scriptfile.read()
                script = toml.loads(data)            
    except IOError:
        print("   Could not open script file:" % scriptName)
    except Exception as e:
        print("   Unknown error.")
        print("   " + str(e))
        sys.exit()
    else:
        if sectionName == None:
            return script
        else:
            return fetchSection(script, sectionName)

# Fetch Section From Script
def fetchSection (script, sectionName='game-start'):

    print(">>> Fetch section: " + sectionName)
    return script[sectionName] if sectionName in script else ""

# スクリプト System セクション読み込み
def readSystemFromScript ():

    return readScript(sysvar_script, "system")

# スクリプト where-am-i 読み込み
def readWhereAmIFromScript ():

    return readScript(sysvar_script, "where-am-i")

# where-am-i
def getWhereAmI ():

    script = readWhereAmIFromScript()
    if sysvar_args.showscript == True: print(script)
    baseImage = "wai.png"
    # saveScreenShot(baseImage)

    result = dict(result=False)

    for waiSection in script:
        print(script[waiSection])
        convictions = script[waiSection]
        for conviction in convictions['convictions']:
            print("    Conviction: " + str(conviction))
            res = findTarget(conviction, baseImage)
            print(res)
            if res["result"] == False:
                break;
        else:
            print("I'm in " + waiSection.capitalize() + ".")
            return dict(result=True, story=waiSection)

    return result

# Get Screen Shot And Save It
def saveScreenShot (saveName, saveSequence=False):

    screenshot = pyautogui.screenshot()

    if saveSequence == True:
        # If temp directory doesn't exist, make temp directory.
        if not os.path.isdir('temp'):
            os.makedirs('temp')

        savedFileNameSeed = datetime.datetime.now()
        savedFileName = savedFileNameSeed.strftime("temp/%Y-%m-%d-%H-%M-%S.png")
        screenshot.save(savedFileName)
        # Create Mosaic Image
        if getTempFileCount() > 15:
            createMosaicImage()
    else:
        screenshot.save(saveName)

    print('>>> Saved screenshot...')

def getTempFileCount ():

    if not os.path.isdir('temp'):
        return 0

    files = os.listdir('temp')
    return len(files)

def createMosaicImage ():

    fileCount = getTempFileCount()

    images = []

    files = os.listdir('temp')
    for file in files:
        images.append(cv2.imread('temp/' + file))
        os.remove('temp/' + file)

    for i in range(fileCount, 25):
        images.append(cv2.imread('no-image.png'))

    print('IMAGE LENGTH: ' + str(len(images)))

    mosaics = imc.build_montages(images, (384, 306), (5, 5))
    print(len(mosaics))
    cv2.imwrite('gattai.png', mosaics[0], [cv2.IMWRITE_PNG_COMPRESSION, 9])

# 認識メソッド
def findTarget (target, base, threshold=0.0):

    # Save screenshot
    saveScreenShot(base)

    if threshold == 0.0: threshold = sysvar_threshold

    target = sysvar_imgdir + "/" + target

    # Confirm the existance of the target file
    if os.path.isfile(target) != True:
        print("ERROR: Could not find target file: " + target)
        return dict(result=False, score=0.0)

    # Confirm the existance of base file
    if os.path.isfile(base) != True:
        print("ERROR: Could not find base file: " + base)
        return dict(result=False, score=0.0)

    # Reading base file and target file
    baseImage = cv2.imread(base, 1)
    greyScaledBaseImage = cv2.cvtColor(baseImage, cv2.COLOR_BGR2GRAY)

    template = cv2.imread(target, 1)
    greyScaledTemplate = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

    # If reduction template flag is True, the image resized to 1/2
    if sysvar_args.reduction_template == True:
        print("    Reduction template to 1/2")
        greyScaledTemplate = imutils.resize(greyScaledTemplate, width = int(greyScaledTemplate.shape[1] * 0.5))

    found = None

    # ブラウザ ZOOM の iterator 生成
    # browserZoom = iter([1.0, 0.90, 0.75, 0.67, 0.50, 0.33, 0.25])
    browserZoom = iter(sysvar_searchzoom)

    for scale in browserZoom:
        print(">>> Resize scale: {0}".format(scale))
        resizedTemplate = imutils.resize(greyScaledTemplate, width = int(greyScaledTemplate.shape[1] * scale))
        (templateHeight, templateWidth) = resizedTemplate.shape[:2]

        # # Debug
        # cv2.imshow("Template", edgedTemplate)
        # time.sleep(0.1)
        # cv2.destroyWindow("Template")

        # Matching process -- アルゴリズムは cv2.TM_CCOEFF でもよい
        result = cv2.matchTemplate(greyScaledBaseImage, resizedTemplate, cv2.TM_CCOEFF_NORMED)
        (minVal, maxVal, minloc, maxLoc) = cv2.minMaxLoc(result)
        print("    Matching result: ({0}, {1}) score = {2}".format(maxLoc[0], maxLoc[1], maxVal))

        # Debug
        if sysvar_args.show_recresult == True:
            clone = np.dstack([greyScaledBaseImage, greyScaledBaseImage, greyScaledBaseImage])
            cv2.rectangle(clone, (maxLoc[0], maxLoc[1]),
                (maxLoc[0] + templateWidth, maxLoc[1] + templateHeight), (0, 0, 255), 2)
            cv2.putText(clone, str(maxVal), (maxLoc[0], maxLoc[1]), cv2.FONT_HERSHEY_PLAIN, 1, (0, 255, 0))
            cv2.imshow("Visualize", clone)
            cv2.waitKey(0)
            cv2.destroyWindow("Visualize")

        # Store largiest value
        if found is None or maxVal > found[0]:
            found = (maxVal, maxLoc, scale, templateHeight, templateWidth)

        # Break the loop if result over the threshold
        if maxVal > threshold:
            break;

    (maxVal, maxLoc, scale, height, width) = found
    print(">>> Final matching result: {0}, {1}, {2}, {3}, {4}".format(maxVal, maxLoc, scale, height, width))
    (startX, startY) = (int(maxLoc[0]), int(maxLoc[1]))
    (endX, endY) = (int((maxLoc[0] + width) * 1), int((maxLoc[1] + height) * 1))

    # Debug
    # cv2.rectangle(baseImage, (startX, startY), (endX, endY), (0, 0, 255), 2)
    # cv2.putText(baseImage, str(maxVal), (startX, startY), cv2.FONT_HERSHEY_PLAIN, 1, (0, 255, 0))
    # cv2.imshow("Image", imutils.resize(baseImage, width = int(baseImage.shape[1] * 0.5)))
    # time.sleep(1)
    # cv2.waitKey(0)

    # res = cv2.matchTemplate(src, temp, cv2.TM_CCOEFF_NORMED)
    # (minval, maxval, minloc, maxloc) = cv2.minMaxLoc(res)
    # (h, w, d) = temp.shape
     
    # rect_1 = (maxloc[0], maxloc[1])
    # rect_2 = (maxloc[0] + w, maxloc[1] + h)
    # print("({0}, {1}) score = {2}".format(maxloc[0], maxloc[1], maxval))
    # print("size ({0}, {1})".format(w, h))

    if maxVal < threshold:
        print("    Could not find target: " + target)
        return dict(result=False)
    else:
        return dict(result=True, score=maxVal, width=width, height=height, top=maxLoc[0], left=maxLoc[1])

# Play Story
def playStory (story):

    # Reading main script
    script = fetchSection(readScript(sysvar_script), story)
    if sysvar_args.showscript == True: print(script)

    res = dict(result=False)

    # Set time out parameter from system parameter
    timeOut = sysvar_timeout
    if "timeout" in script:
        timeOut = script["timeout"]
    print(timeOut)

    # Sequence process
    if "loopmax" in script and "loopquit" in script:
        loopMax = script["loopmax"]
        loopQuit = script["loopquit"]
        print("%(1)s, %(2)s" % {"1":loopMax, "2":loopQuit})
        if "sequence" in script:
            res = playSequence(script, timeOut)

            print("+++ playSequence")
            print(res)
            print("recovers" in script)

            # シーケンスに失敗したらリカバー処理
            if res["result"] == False and "recovers" in script:
                res = playRecover(script, timeOut)

    # Case
    elif "cases" in script:
        print(script["cases"])
        res = playCase(script, timeOut)
        if res["result"] == True:
            print("Case Succeed.")

    # Any
    elif "any" in script:
        print(script["any"])
        res = playAny(script)
        if res["result"] == True:
            print("Any Succeed.")

    # Single
    else:
        res = playSequence(script, timeOut)

        # シーケンスに失敗したらリカバー処理
        if res["result"] == False and "recovers" in script:
            print("Recovery is working.")
            res = playRecover(script, timeOut)

    return res

# Play Case
def playCase (script, timeOut):

    for case in script["cases"]:
        print(script["cases"][case])
        conditions = script["cases"][case]
        print(conditions)
        if "conditions" in conditions:

            # シーケンス毎のタイムアウト
            retry = int(getListAttribute(conditions, "retry", 0))
            print(retry)

            for condition in conditions["conditions"]:
                # シーケンス全体の delay 設定 - あれば
                sequenceDelay = conditions["sequence-delay"] if "sequence-delay" in conditions else 0
                print("Sequence Delay: " + str(sequenceDelay))
                time.sleep(sequenceDelay)
                res = findTarget(condition, sysvar_savess)
                print(res)
                if res['result'] == False:
                    break
            else:
                todores = toDoOrNotToDo(case, 0, conditions)
                print(todores)

                if "sequence" in conditions and todores["result"] == True:
                    res = playSequence(conditions, timeOut)
                    print(conditions)

                    # シーケンスに失敗したらリカバー処理
                    if res["result"] == False and "recovers" in conditions:
                        print("YABASU!!!")
                        res = playRecover(conditions, timeOut)

    print("+++ BREAK")
    return dict(result=False)

# Play Any
def playAny (script):

    if not "quit-conditions" in script and not "quit-conditions-or" in script:
        print("Could not find quit conditions.")
        return dict(result=False)

    while True:
        # Set timeout forcibly for 1
        res = playList(script, "any", 1, True)
        print(res)

        if "quitSequence" in res and res["quitSequence"] == True:
            return res

    return dict(result=False)

# Play Sequence
def playSequence (script, timeOut):

    return playList(script, "sequence", timeOut)

# Play Sequence Block
def playSequenceBlock (sequenceBlockName, timeOut):

    script = fetchSection(readScript(sysvar_script), sequenceBlockName)
    print(script)

    if len(script) == 0:
        return dict(result=True)

    return playList(script, "sequence", timeOut)

# Play Quit Sequence
def playQuitSequence (script, timeOut):

    return playList(script, "quit-sequence", timeOut)

# Play Recover
def playRecover (script, timeOut):

    return playList(script, "recovers", timeOut)

# Play Row Script
def playList (script, scriptKey, timeOut, allSkipForce=False):

    # Check the key in the script
    if scriptKey not in script:
        print("Could not find key: " + scriptKey)
        return dict(result=False)

    # Check enable flag
    if "enable" in script and script["enable"] == 1:
        print("--- " + scriptKey + " is disabled")
        return dict(result=True)

    # Set time out for sequence
    timeOut = script["timeout"] if "timeout" in script else timeOut

    # Set delay for sequence
    sequenceDelay = script["sequence-delay"] if "sequence-delay" in script else 0

    # Sequence
    for snippets in script[scriptKey]:
        resset = playSnipetInList(snippets, script, scriptKey, timeOut, allSkipForce, sequenceDelay)

        # If result has quit status, quit this loop.
        if "quit" in resset and resset["quit"] == True:
            return resset
    else:
        return resset

    return dict(result=False)

def playSnipetInList (snippets, script, scriptKey, timeOut, allSkipForce, sequenceDelay):

    snippets = snippets.split(":")
    print(snippets)

    resset = dict(result=False)
    snippet = snippets[0]
    print(snippet)

    # Script block processing
    scriptBlock = getListAttribute(snippets, "scriptblock", "")
    print("scriptblock = " + scriptBlock)
    if len(scriptBlock):
        playSequenceBlock(scriptBlock, timeOut)
        return dict(result=True, goNext=True)

    # Set skip force flag
    skipForce = "skipforce" in snippets if True else False
    skipForce = True if allSkipForce == True else skipForce
    print(skipForce)

    # Delay for each snippet
    eachDelay = float(getListAttribute(snippets, "delay", sequenceDelay))
    print("  delay = " + str(eachDelay))

    # Timeout for each snippet
    timeOut = int(getListAttribute(snippets, "timeout", timeOut))
    print("  timeout = " + str(timeOut))

    # Threshold for each snippet
    threshold = float(getListAttribute(snippets, "threshold", sysvar_threshold))
    print("  threshold = " + str(threshold))

    # Quit direction
    quitDirection = getListAttribute(snippets, "quitdirection")
    print("  quitdirection = " + quitDirection)

    # Read snippet by main script
    scriptSnippet = fetchSection(readScript(sysvar_snippet_script), snippet)
    print(scriptSnippet)
    if "target" in scriptSnippet: print(scriptSnippet['target'])

    # Slack image title
    title = scriptSnippet["title"] if "title" in scriptSnippet else "No Title"

    # If snippet has timeout, system use own timeout
    timeOut = scriptSnippet['timeout'] if "timeout" in scriptSnippet else timeOut

    # Check if the action is implemented
    thismodule = sys.modules[__name__]
    if not hasattr(thismodule, scriptSnippet['action']):
        print("Method %s is not implemented." % scriptSnippet['action'])
        return dict(result=False, quit=True)
    else:
        actionMethod = getattr(thismodule, scriptSnippet['action'])
    # try:
    #     thismodule = sys.modules[__name__]
    #     actionMethod = getattr(thismodule, scriptSnippet['action'])
    # except AttributeError:
    #     raise NotImplementedError("Method %s not implemented." % scriptSnippet['action'])

    options = {}
    if "options" in scriptSnippet:
        for option in scriptSnippet['options']:
            print("    Option: " + str(option))
            if option in scriptSnippet:
                options[option] = scriptSnippet[option]
                print(scriptSnippet[option])
                break
        else:
            print("Could not find option: " + option + "...")

    # タイムアウトまで処理実行
    for i in range(timeOut):
        print("    TET => %d" % i)
        time.sleep(eachDelay)

        if "target" in scriptSnippet:
            res = findTarget(scriptSnippet['target'], sysvar_savess, threshold)
            print(res)
        else:
            # Save screenshot
            saveScreenShot(sysvar_savess)
            res = dict(result=True)

        # If find the target, execute the specified action.
        if res['result'] == True:
            # If sysvar_saveseq flag is on, Save screenshot.
            if sysvar_saveseq == True: saveScreenShot(sysvar_savess, True)
            # Add snipet options
            res.update(options)
            actionMethod(**res)
            t = threading.Thread(target=postSlack, args=(sysvar_savess, title))
            t.start()
            return dict(result=True)
        time.sleep(0.01)
    else:
        # If script has quit conditions, check conditions after missing target.
        if scriptKey != "quit-sequence" and "quit-conditions" in script or "quit-conditions-or" in script:
            res = checkQuitCondition(script["quit-conditions"], sequenceDelay) if "quit-conditions" in script else \
                  checkQuitConditionOr(script["quit-conditions-or"], sequenceDelay)
            if "quitSequence" in res and res["quitSequence"] == True:
                resset = playQuitSequence(script, timeOut)
                resset["quitSequence"] = True
                resset["quit"] = True
                return resset
            elif res["result"] == True:
                return dict(result=True, goNext=True)

        # If skip force flag is enable, skip to next list
        if skipForce == True:
            print("Skip force option enabled.")
            return dict(result=False, goNext=True)
        elif quitDirection:
            resset = playQuitDirection(quitDirection)
            resset["quit"] = True
            return resset
        else:
            return dict(result=False, quit=True)

# Check Quit Condition
def checkQuitCondition (scriptQuitConditions, sequenceDelay=0):

    for condition in scriptQuitConditions:
        time.sleep(sequenceDelay)
        res = findTarget(condition, sysvar_savess)
        print(res)
        if res['result'] == False:
            break
    else:
        if res["result"] == True:
            return dict(result=True, quitSequence=True)

    return dict(result=False)

# Check Quit Condition OR
def checkQuitConditionOr (scriptQuitConditions, sequenceDelay=0):

    for condition in scriptQuitConditions:
        time.sleep(sequenceDelay)
        res = findTarget(condition, sysvar_savess)
        print(res)
        if res['result'] == True:
            return dict(result=True, quitSequence=True)

    return dict(result=False)

# タイムアウト時に実行
def playQuitDirection (snippet, sequenceDelay=0):

    # メインスクリプトに記載されているスニペットの読み込み
    scriptSnippet = fetchSection(readScript(sysvar_snippet_script), snippet)
    if len(scriptSnippet) == 0:
        print("Could not find a snippet: " + snippet)
        return dict(result=False)

    print(scriptSnippet)
    print(scriptSnippet['target'])

    # アクションが実装されているかをチェック
    thismodule = sys.modules[__name__]
    if not hasattr(thismodule, scriptSnippet['action']):
        print("Method %s is not implemented." % scriptSnippet['action'])
        return dict(result=False)
    else:
        actionMethod = getattr(thismodule, scriptSnippet['action'])

    res = findTarget(scriptSnippet['target'], sysvar_savess)
    print(res)

    # 指定されたアクションを実行
    if res['result'] == True:
        # If sysvar_saveseq flag is on, Save screenshot.
        if sysvar_saveseq == True: saveScreenShot(sysvar_savess, True)
        actionMethod(**res)
        time.sleep(sequenceDelay)
        return dict(result=True)

    return dict(result=False)

# Post image
def postSlack (imgName, title):

    if sysvar_bottom == 0: return

    # Open an image and cut it off
    imgOrg = Image.open(imgName)
    thumbFile = "ss_thumb.png"
    rect = (sysvar_top, sysvar_left, sysvar_bottom, sysvar_right)
    imgCutoff = imgOrg.crop(rect)
    imgCutoff.thumbnail((sysvar_slackthumbssize, sysvar_slackthumbssize), Image.ANTIALIAS)
    imgCutoff.save(thumbFile, "png")

    # Send image
    with open(thumbFile, 'rb') as f:
        param = {'token': sysvar_slacktoken, 'channels': sysvar_slackchannel, 'title': title, 'filetype': 'auto'}
        r = requests.post("https://slack.com/api/files.upload", params=param,files={'file': f})
        print(param)
        print(r)

# リスト内の属性を取得
def getListAttribute (snippets, key, default=""):

    value = default
    r = re.compile(key + "*")
    temp = [x for x in snippets if r.match(x)]
    # print(temp)

    if isinstance(temp, list) and len(temp) > 0:
        temp = temp[0].split("=")
        # print(temp)
        value = temp[1].strip() if len(temp) > 1 else default
        # print(value)

    return value

def toDoOrNotToDo (sequenceKey, runAfter=0, script=""):

    if not script == "":
        if "run-after" not in script:
            return dict(result=True)
        runAfter = script["run-after"]

    res = setRunAfter(sequenceKey, runAfter)

    if res["result"] == True:
        return dict(result=True)

    res = getRunAfter(sequenceKey)

    return res

def setRunAfter (sequenceKey, runAfter):

    baseTime = datetime.datetime.now()
    print(baseTime)

    global sysvar_runafter
    if sequenceKey in sysvar_runafter:
        print("Exist run after: " + sequenceKey)
        return dict(result=False)

    sysvar_runafter[sequenceKey] = baseTime + datetime.timedelta(minutes=runAfter)
    print(sysvar_runafter)
    return dict(result=True)

def getRunAfter (sequenceKey):

    global sysvar_runafter
    if sequenceKey not in sysvar_runafter:
        print("Could not find key: " + sequenceKey)
        return dict(result=False)

    baseTime = datetime.datetime.now()
    expireTime = sysvar_runafter[sequenceKey]
    delta = expireTime - baseTime
    lastMins = (delta.seconds/60)

    if delta.days < 0:
        del sysvar_runafter[sequenceKey]
        return dict(result=True)
    else:
        return dict(result=False, last=lastMins)

# マウス移動＆クリック
def moveAndClick (**options):

    displayMagnification = 2 if sysvar_ratina == True else 1
    pyautogui.moveTo((options.get('top')/displayMagnification) + (options.get('width')/(displayMagnification*2)),
                     (options.get('left')/displayMagnification) + (options.get('height')/(displayMagnification*2)),
                     2)
    pyautogui.click()
    pyautogui.moveTo(10, 10) # 10, 10 for avoid fail-safe

# マウス移動＆ダブルクリック
def moveAndDoubleClick (**options):

    displayMagnification = 2 if sysvar_ratina == True else 1
    pyautogui.moveTo((options.get('top')/displayMagnification) + (options.get('width')/(displayMagnification*2)),
                     (options.get('left')/displayMagnification) + (options.get('height')/(displayMagnification*2)),
                     2)
    pyautogui.doubleClick()
    pyautogui.moveTo(10, 10) # 10, 10 for avoid fail-safe

# マウス移動＆クリックで画面アクティブ＆クリック
def moveAndActiveAndClick (**options):

    displayMagnification = 2 if sysvar_ratina == True else 1
    pyautogui.moveTo((options.get('top')/displayMagnification) + (options.get('width')/(displayMagnification*2)),
                     (options.get('left')/displayMagnification) + (options.get('height')/(displayMagnification*2)),
                     2)
    pyautogui.click()
    time.sleep(0.2)
    pyautogui.click()
    pyautogui.moveTo(10, 10)

# 認識されたらマウス移動＆クリック
def moveNClickIfFindIt (**options):

    displayMagnification = 2 if sysvar_ratina == True else 1
    pyautogui.moveTo((options.get('top')/displayMagnification) + (options.get('width')/(displayMagnification*2)),
                     (options.get('left')/displayMagnification) + (options.get('height')/(displayMagnification*2)), 2)
    pyautogui.click()
    pyautogui.moveTo(10, 10)

# Mouse click
def clickCenter (**options):

    displayMagnification = 2 if sysvar_ratina == True else 1

    if sysvar_right == 0:
        width, hegith = pyautogui.size()
        print(width, hegith)
        pyautogui.moveTo(width/2, hegith/2, 2)        
    else:
        pyautogui.moveTo((sysvar_top/displayMagnification) + ((sysvar_right-sysvar_left)/(displayMagnification*2)),
                         (sysvar_left/displayMagnification) + ((sysvar_bottom-sysvar_top)/(displayMagnification*2)),
                         2)
    pyautogui.click()
    pyautogui.moveTo(10, 10) # 10, 10 for avoid fail-safe

# スクロール
def scrollPage (**options):

    displayMagnification = 2 if sysvar_ratina == True else 1
    pyautogui.moveTo((options.get('top')/displayMagnification) + (options.get('width')/(displayMagnification*2)),
                     (options.get('left')/displayMagnification) + (options.get('height')/(displayMagnification*2)),
                     2)
    pyautogui.click()
    pyautogui.scroll(options.get('scroll'))
