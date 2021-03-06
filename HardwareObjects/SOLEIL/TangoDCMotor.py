
import logging
import time

from HardwareRepository.BaseHardwareObjects import Device
from HardwareRepository.Command.Tango import TangoCommand

from qt import qApp

class TangoDCMotor(Device):
    
    MOVESTARTED    = 0
    NOTINITIALIZED = 0
    UNUSABLE       = 0
    READY          = 2
    MOVING         = 4
    ONLIMITS       = 1

    stateDict = {
	 "UNKNOWN": 0,
	 "OFF":     0,
	 "ALARM":   1,
	 "FAULT":   1,
	 "STANDBY": 2,
	 "RUNNING": 4,
	 "MOVING":  4,
	 "ON":      2}

    def __init__(self, name):

        # State values as expected by Motor bricks

	Device.__init__(self, name)
	self.GUIstep = 0.1

    def _init(self):
	
        self.positionValue = 0.0
        self.stateValue    = 'UNKNOWN'
        self.threshold     = 0.0018   # default value. change it with property threshold in xml

	self.old_value = 0.
	self.tangoname = self.getProperty("tangoname")
	threshold      = self.getProperty("threshold")

        try:
	   self.dataType    = self.getProperty("datatype")
	   logging.getLogger("HWR").info("TangoDCMotor dataType found in config, it is %s", self.dataType)
        except:
	   self.dataType    = "float"

        if threshold is not None:
            try:
               self.threshold = float(threshold)
            except:
               pass

	self.setIsReady(True)

	self.positionChan = self.getChannelObject("position") # utile seulement si positionchan n'est pas defini dans le code
	self.stateChan    = self.getChannelObject("state")    # utile seulement si statechan n'est pas defini dans le code

	self.positionChan.connectSignal("update", self.positionChanged) 
	self.stateChan.connectSignal("update", self.motorStateChanged)   

    def positionChanged(self, value):
        self.positionValue = value
	if abs(value - self.old_value ) > self.threshold:
	    try:
		self.emit('positionChanged', (value,))
	    except:
		logging.getLogger("HWR").error("%s: TangoDCMotor not responding, %s", self.name(), '')
	self.old_value = value
    
    def isReady(self):
	return self.stateValue == 'STANDBY'
	
    def connectNotify(self, signal):
	if signal == 'hardwareObjectName,stateChanged':
	    self.motorStateChanged(TangoDCMotor.stateDict[self.stateValue])
	elif signal == 'limitsChanged':
	    self.motorLimitsChanged()
	elif signal == 'positionChanged':
	    self.motorPositionChanged(self.positionValue)
	self.setIsReady(True)
    
    def motorState(self):
	return TangoDCMotor.stateDict[self.stateValue]
    
    def motorStateChanged(self, state):
        self.stateValue = str(state)
	self.setIsReady(True)
        logging.info("motor state changed. it is %s " % self.stateValue)
	self.emit('stateChanged', (TangoDCMotor.stateDict[self.stateValue], ))
	
    def getState(self):
	state = self.stateValue
	return TangoDCMotor.stateDict[self.stateValue]
    
    def getLimits(self):
        try:
           info = self.positionChan.getInfo() 
           max = float(info.max_value)
           min = float(info.min_value)
	   logging.getLogger("HWR").info("TangoDCMotor.getLimits: %.4f %.4f" % (min,max))
	   return [min,max]
        except:
	   logging.getLogger("HWR").info("TangoDCMotor.getLimits: Cannot get limits for %s" % self.name())
	   return [-1,1]
	
    def motorLimitsChanged(self):
	self.emit('limitsChanged', (self.getLimits(), )) 
		      
    def motorIsMoving(self):
	return( self.stateValue == "RUNNING" or self.stateValue == "MOVING" )

    def motorMoveDone(self, channelValue):
       if self.stateValue == 'STANDBY':
	  self.emit('moveDone', (self.tangoname,"tango" ))
	  
    def motorPositionChanged(self, absolutePosition):
	self.emit('positionChanged', (absolutePosition, ))

    def syncQuestionAnswer(self, specSteps, controllerSteps):
	return '0' # This is only for spec motors. 0 means do not change anything on sync
    
    def getPosition(self):
	pos = self.positionValue
	return pos

    def getDialPosition(self):
        return self.getPosition()
    
    def syncMove(self, position):
	prev_position      = self.getPosition()
	self.positionValue = position

	while self.stateValue == "RUNNING" or self.stateValue == "MOVING": # or self.stateValue == SpecMotor.MOVESTARTED:
	    qApp.processEvents(100)

    def moveRelative(self, position):
        old_pos = self.positionValue
        self.positionValue = old_pos + position
        self.positionChan.setValue( self.convertValue(self.positionValue) )
        logging.info("TangoDCMotor: movingRelative. motor will go to %s " % str(self.positionValue))

        while self.stateValue == "RUNNING" or self.stateValue == "MOVING":
            qApp.processEvents(100)
        
    def convertValue(self, value):
        logging.info("TangoDCMotor: converting value to %s " % str(self.dataType))
        retvalue = value
        if self.dataType in [ "short", "int", "long"]:
            retvalue = int(value)
        return(retvalue)

    def syncMoveRelative(self, position):
        old_pos = self.positionValue
        self.positionValue = old_pos + position
        self.positionChan.setValue( self.convertValue(self.positionValue) )

        while self.stateValue == "RUNNING" or self.stateValue == "MOVING":
            qApp.processEvents(100)
        
    def getMotorMnemonic(self):
        return self.name()

    def move(self, absolutePosition):
        """Move the motor to the required position

        Arguments:
        absolutePosition -- position to move to
        """
        if type(absolutePosition) != float and type(absolutePosition) != int:
            logging.getLogger("TangoClient").error("Cannot move %s: position '%s' is not a number. It is a %s", self.tangoname, absolutePosition, type(absolutePosition))
            
        logging.getLogger("HWR").info("TangoDCMotor.move to absolute position: %.3f" % absolutePosition)
        logging.getLogger("TangoClient").error("TangoDCMotor move. Trying to go to %s: that is a '%s'", absolutePosition, type(absolutePosition))
        self.positionChan.setValue( self.convertValue(absolutePosition) )

    def stop(self):
        logging.getLogger("HWR").info("TangoDCMotor.stop")
        stopcmd = self.getCommandObject("Stop")()
        if not stopcmd:
           stopcmd = TangoCommand("stopcmd","Stop",self.tangoname)
        stopcmd()

    def isSpecConnected(self):
        logging.getLogger().debug("%s: TangoDCMotor.isSpecConnected()" % self.name())
        return TruehardwareObjectName,
    
