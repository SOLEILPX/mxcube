
from qt import *
import logging
import HutchMenuBrick


__category__ = 'SOLEIL'

###
### Sample centring brick
###
class SoleilHutchMenuBrick(HutchMenuBrick.HutchMenuBrick):

    def __init__(self, *args):
        HutchMenuBrick.HutchMenuBrick.__init__(self, *args)

        self.buttonBeamPosition = QToolButton(self.sampleCentreBox)
        self.buttonBeamPosition.setUsesTextLabel(True)
        self.buttonBeamPosition.setTextLabel("CheckBeam")
        self.buttonBeamPosition.setMinimumSize(QSize(75,50))
        self.buttonBeamPosition.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        QObject.connect(self.buttonBeamPosition, SIGNAL('clicked()'), self.beamPositionCheck)
        #HorizontalSpacer3(self.sampleCentreBox)

    def beamPositionCheck(self):
        self.minidiff.beamPositionCheck()
        
