#! /usr/bin/env python

import opals

from PyQt5.QtCore import QObject, pyqtSignal

class ProgressEmitter(QObject):
    progressChanged = pyqtSignal(int)
    stageChanged = pyqtSignal(str)

class Control(opals.Types.IControlObject):
    def __init__(self, emitter):
        super().__init__()
        self.stages = None
        self.prefix = None
        self.stepCount = None
        self.emitter = emitter

    def setStages(self, stages):
        self.stages = stages  # store stage message string list

    def setCurrStage(self, stageIdx):
        self.prefix = f"{stageIdx+1}.stage: {self.stages[stageIdx]}"
        self.emitter.stageChanged.emit(self.prefix)

    def setSteps(self, stepCount):
        self.stepCount = stepCount 

    def setCurrStep(self, currStep):
        perc = int(100*currStep/float(self.stepCount))
        self.emitter.progressChanged.emit(perc)
        if currStep == self.stepCount:
            print()  # add line feed

    def log(self, loglevel, threadid, message):
        # only output error messages
        if loglevel <= opals.Types.LogLevel.error:
            print(f"{loglevel}: {message}")