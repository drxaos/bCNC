# DISCLAIMER
# ~~~~~~~~~~
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT
# NOT LIMITED TO, IMPLIED WARRANTIES OF MERCHANTABILITY, OF
# SATISFACTORY QUALITY, AND FITNESS FOR A PARTICULAR PURPOSE
# OR USE ARE DISCLAIMED. THE COPYRIGHT HOLDERS AND THE
# AUTHORS MAKE NO REPRESENTATION THAT THE SOFTWARE AND
# MODIFICATIONS THEREOF, WILL NOT INFRINGE ANY PATENT,
# COPYRIGHT, TRADE SECRET OR OTHER PROPRIETARY RIGHT.
#
# LIMITATION OF LIABILITY
# ~~~~~~~~~~~~~~~~~~~~~~~
# THE COPYRIGHT HOLDERS AND THE AUTHORS SHALL HAVE NO
# LIABILITY FOR DIRECT, INDIRECT, SPECIAL, INCIDENTAL,
# CONSEQUENTIAL, EXEMPLARY, OR PUNITIVE DAMAGES OF ANY
# CHARACTER INCLUDING, WITHOUT LIMITATION, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES, LOSS OF USE, DATA OR PROFITS,
# OR BUSINESS INTERRUPTION, HOWEVER CAUSED AND ON ANY THEORY
# OF CONTRACT, WARRANTY, TORT (INCLUDING NEGLIGENCE), PRODUCT
# LIABILITY OR OTHERWISE, ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH
#!/usr/bin/python
# -*- coding: ascii -*-

# Author: Mario Basz
# mariob_1960@yahoo.com.ar
# Date: 10 may 2018

__author__ = "Mario Basz"
__email__  = "mariob_1960@yahoo.com.ar" 

# Version 0.2

# A special thanks to Vasilis Viachoudis, Filippo Rivato and Buschhardt 

#Here import the libraries you need, these are necessary to modify the code  
import math
import os.path
import re
from CNC import CNC,Block
from ToolsPage import Plugin
#==============================================================================
# My plugin
#==============================================================================
from math import pi, sqrt, sin, cos, asin, acos, atan2, hypot, degrees, radians, copysign, fmod
class Tool(Plugin):
	# WARNING the __doc__ is needed to allow the string to be internationalized
	__doc__ = _("""This is my Helical Descent""")			#<<< This comment will be show as tooltip for the ribbon button
	def __init__(self, master):
		Plugin.__init__(self, master,"Helical")
		#Helical_Descent: is the name of the plugin show in the tool ribbon button
		self.icon = "Helical"			#<<< This is the name of gif file used as icon for the ribbon button. It will be search in the "icons" subfolder
		self.group = "CAM"	#<<< This is the name of group that plugin belongs
		#Here we are creating the widgets presented to the user inside the plugin
		#Name, Type , Default value, Description
		self.variables = [			#<<< Define a list of components for the GUI
			("name"    ,    "db" ,    "", _("Name")),							#used to store plugin settings in the internal database
			("Sel_Blocks", "bool" , "False", _("Selected Block")),
			("X", "mm" ,  0.00, _("X Initial")),
			("Y", "mm" ,  0.00, _("Y Initial")),
			("Z", "mm" ,  0.00, _("Z Initial")),
            ("CutDiam" ,"float", 1.50, _("Diameter Cut")),
			("endmill",   "db" ,    "", _("End Mill")),
	#		("RadioHelix", "mm" ,  0.80, _("Helicoid Radius")),				#a variable that will be converted in mm/inch based on bCNC settting
			("Pitch"     ,  "mm" ,  0.10, _("Drop by lap")),			#an integer variable
			("Depth"   , "mm" ,     3.00, _("Final Depth")),			#a float value variable
			("Mult_Feed_Z",  "float" ,1.0, _("Z Feed Multiplier")),
			("HelicalCut" ,  "Helical Cut,Internal Right Thread,Internal Left Thread,External Right Thread,External Left Thread", "Helical Cut",_("Helical Type")),
			("Entry" ,"Center,Edge" , "Center", _("Entry and Exit")),
            ("ClearanceEntry" ,"float", 0.2, _("Entry Edge Clearance")),
            ("ClearanceExit" ,"float", 0.2, _("Exit Edge Clearance")),
			("ReturnToSafeZ" ,"bool" , "True", _("Returns to safe Z")),

		#	("Text"    , "text" ,    "Free Text", _("Text description")),		#a text input box
		#	("CheckBox", "bool" ,  False, _("CheckBox description")),			#a true/false check box
		#	("OpenFile", "file" ,     "", _("OpenFile description")),			#a file chooser widget
		#	("ComboBox", "Item1,Item2,Item3" , "Item1", _("ComboBox description"))	#a multiple choice combo box 
		]
		self.buttons.append("exe")  #<<< This is the button added at bottom to call the execute method below

	# Calc line length -----------------------------------------------------
	def calcSegmentLength(self, xyz):
		if xyz:
			p1 = xyz[0]
			p2 = xyz[1]
			return math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2 + (p2[2]-p1[2])**2)
		else:
			return 0

	#Extract all segments from commands ------------------------------------
	def extractAllSegments(self, app,selectedBlock):
		allSegments = []
		allBlocks = app.gcode.blocks

		for bid in selectedBlock:
			bidSegments = []
			block = allBlocks[bid]
			if block.name() in ("Header", "Footer"): continue
			#if not block.enable : continue
			app.gcode.initPath(bid)
			for line in block:
				try:
					cmd = app.cnc.breakLine(app.gcode.evaluate(app.cnc.compileLine(line)))
				except:
					cmd = None

				if cmd:
					app.cnc.motionStart(cmd)
					xyz = app.cnc.motionPath()
					app.cnc.motionEnd()

					if xyz:
						#exclude if fast move or z only movement
						G0 =('g0' in cmd) or ('G0' in cmd)
						Zonly = (xyz[0][0] == xyz[1][0] and xyz[0][1] == xyz[1][1])
						exclude = G0 or Zonly

						#save length for later use
						segLenth = self.calcSegmentLength(xyz)

						if len(xyz) < 3:
							bidSegments.append([xyz[0],xyz[1],exclude,segLenth])
						else:
							for i in range(len(xyz)-1):
								bidSegments.append([xyz[i],xyz[i+1],exclude,segLenth])
			#append bidSegmentes to allSegmentes
			allSegments.append(bidSegments)

		#Disabled used block
		for bid in selectedBlock:
			block = allBlocks[bid]
			if block.name() in ("Header", "Footer"): continue
			block.enable = True

		return allSegments

	# ----------------------------------------------------------------------
	# This method is executed when user presses the plugin execute button 
	# ----------------------------------------------------------------------
	def execute(self, app):
		name = self["name"]
		if not name or name=="default": name="Default Name"
		sel_Blocks = self["Sel_Blocks"]
		#Get inputs
		x = self["X"]
		y = self["Y"]
		z = self["Z"]
		if z == "":
			z=CNC.vars["surface"]

		cutDiam = self["CutDiam"]
		cutRadius = cutDiam/2.0
		if self["endmill"]:
			self.master["endmill"].makeCurrent(self["endmill"])
		toolDiam = CNC.vars["diameter"]
		#Radio = self["RadioHelix"]
		pitch = self["Pitch"]
		Depth = self["Depth"]
		Mult_F_Z = self["Mult_Feed_Z"]
		helicalCut = self["HelicalCut"]
		clearanceEntry = self["ClearanceEntry"]
		clearanceExit = self["ClearanceExit"]
		clearance = clearanceEntry
		entry = self["Entry"]
		returnToSafeZ = self["ReturnToSafeZ"]

		toolDiam = CNC.vars['diameter']
		toolRadius = toolDiam/2.0
		Radio = cutRadius - toolRadius
		if(Radio < 0): Radio = 0

		toolDiam = CNC.vars['diameter']
		toolRadius = toolDiam/2.0
		Radio = cutRadius - toolRadius

		if clearanceEntry =="":
			clearanceEntry =0 
		if clearanceExit =="":
			clearanceExit =0 

		if helicalCut == "Helical Cut":
			turn = 2
			p="HelicalCut "
		elif helicalCut == "Internal Right Thread":
			turn = 2
			p= "IntRightThread "
		elif helicalCut == "Internal Left Thread":
			turn = 3
			p= "IntLeftThread "
		elif helicalCut == "External Right Thread":
			Radio = cutRadius + toolRadius
			turn = 2
			p= "ExtRightThread "
		elif helicalCut == "External Left Thread":
			Radio = cutRadius + toolRadius
			turn = 3
			p= "ExtLeftThread "

# 		------------------------------------------------------------------------------------------------------------------		
		#Check inputs
		if sel_Blocks == 0:
			if x == "" or y == "" :
				app.setStatus(_("If block selected false, please make a value of x"))
				return

		elif helicalCut == "":
			app.setStatus(_("Helical Abort: Please select helical type"))
			return

		elif cutDiam < toolDiam or cutDiam == "":
			app.setStatus(_("Helical Abort: Helix diameter must be greater than the end mill"))
			return

		elif cutDiam <= 0:
			app.setStatus(_("Helical Abort: Helix diameter must be positive"))
			return

		elif pitch <= 0 or pitch =="":
			app.setStatus(_("Helical Abort: Drop must be greater than 0"))
			return

		elif Mult_F_Z <= 0 or Mult_F_Z == "":
			app.setStatus(_("Helical Abort: Z Feed Multiplier must be greater than 0"))
			return

		elif entry == "":
			app.setStatus(_("Helical Abort: Please selecte Entry and Exit type"))
			return

		elif clearanceEntry < 0 or clearanceEntry == "":
			app.setStatus(_("Helical Abort: Entry Edge Clearence may be positive"))
			return

		elif clearanceExit < 0 or clearanceExit == "":
			app.setStatus(_("Helical Abort: Exit Edge Clearence may be positive"))
			return
# 		------------------------------------------------------------------------------------------------------------------		
		#Initialize blocks that will contain our gCode
		blocks = []
		#block = Block(name)
		block = Block( p + str(cutDiam) + " Pitch " + str(pitch) + " Bit " + str(toolDiam) + " depth " + str(Depth))
		
		cutFeed = CNC.vars["cutfeedz"]	#<<< Get cut feed Z for the current material
		cutFeedMax = CNC.vars["cutfeed"] #<<< Get cut feed XY for the current material
# 		------------------------------------------------------------------------------------------------------------------
		# Get selected blocks from editor
		selBlocks = app.editor.getSelectedBlocks()
		if not selBlocks:
			app.editor.selectAll()
			selBlocks = app.editor.getSelectedBlocks()

		if not selBlocks:
			if sel_Blocks == 1:
				app.setStatus(_("Helical abort: Please select some path"))
				return
# 		------------------------------------------------------------------------------------------------------------------
		# Get selected blocks from editor
		if sel_Blocks == 1:
			selBlocks = app.editor.getSelectedBlocks()
			if not selBlocks:
				app.editor.selectAll()
				selBlocks = app.editor.getSelectedBlocks()

			#Get all segments from gcode
			allSegments = self.extractAllSegments(app,selBlocks)

			#Create holes locations
			allHoles=[]
			for bidSegment in allSegments:
				if len(bidSegment)==0:
					continue

				bidHoles = []
				for idx, anchor in enumerate(bidSegment):
					if idx ==2:
						newHolePoint = (anchor[0][0],anchor[0][1],anchor[0][2])
						bidHoles.append(newHolePoint)


				#Add bidHoles to allHoles
				allHoles.append(bidHoles)

# 		------------------------------------------------------------------------------------------------------------------
			holesCount = 0
			for bid in allHoles:
				for xH,yH,zH in bid:
					x = xH
					y = yH

# 		------------------------------------------------------------------------------------------------------------------
#		 Init: Adjust feed and rapid move to Z safe 
		
		if Mult_F_Z is"":
			Mult_F_Z = 1

		if Mult_F_Z == 0:
			Mult_F_Z = 1
	
		if Mult_F_Z * cutFeed > cutFeedMax:
			cutFeed = cutFeedMax
		else:
			cutFeed = cutFeed*Mult_F_Z

		block.append(CNC.zsafe()) 			#<<< Move rapid Z axis to the safe height in Stock Material

#		 Move rapid to X and Y coordinate
		if helicalCut == "Helical Cut" or helicalCut == "Internal Right Thread" or helicalCut == "Internal Left Thread":
			if entry == "Center":
				block.append(CNC.grapid(x,y))
			else:
				block.append(CNC.grapid(x-Radio+clearance ,y))

		if helicalCut == "External Right Thread" or helicalCut == "External Left Thread":
			if entry == "Center":
				clearance = 0.0
			block.append(CNC.grapid(x-Radio-clearance ,y))

		#cutFeed = int(cutFeed)
		block.append(CNC.fmt("f",cutFeed))	#<<< Set cut feed
	#	block.append(CNC.gline(x,y)
	#    while (z < 1):
		block.append(CNC.zenter(z))
		block.append(CNC.gline(x-Radio,y))
	#	cutFeed = int((CNC.vars["cutfeed"]	+ CNC.vars["cutfeedz"])/2)	#<<< Get cut feed for the current material

		#cutFeed = int(cutFeed)
		block.append(CNC.fmt("F",cutFeed))	#<<< Set cut feed
		

#-----------------------------------------------------------------------------------------------------
	#	Uncomment for first flat pass
		if helicalCut == "Helical Cut":
			block.append(CNC.gcode(turn, [("X",x-Radio),("Y",y),("Z", z),("I",Radio), ("J",0)]))
#-----------------------------------------------------------------------------------------------------
		if (z < Depth):
			pitch = -pitch

			while ((z-pitch) < Depth) :
				z = z-pitch
				block.append(CNC.gcode(turn, [("X",x-Radio),("Y",y),("Z", z),("I",Radio), ("J",0)]))

		else:
			while ((z-pitch) >= Depth) :
				z = z-pitch
				block.append(CNC.gcode(turn, [("X",x-Radio),("Y",y),("Z", z),("I",Radio), ("J",0)]))

		#Target Level
		if entry == "Center":
			clearanceExit = 0.0	
		clearance = clearanceExit
		alpha= round(Depth / pitch, 4 ) - round(Depth / pitch, 0)
		alpha = alpha * 2*pi 
		Radiox = Radio * cos(alpha)
		Radioy = Radio * sin(alpha)
		xsi = Radiox - clearance* cos(alpha)
		ysi =Radioy - clearance* sin(alpha)
		xse = Radiox + clearance* cos(alpha)
		yse =Radioy + clearance* sin(alpha)
		z = Depth



		if helicalCut == "Helical Cut":
			block.append(CNC.gcode(turn, [("X",x-Radio),("Y",y),("Z", z),("I",Radio), ("J",0)]))
			#Last flat pass
			block.append(CNC.gcode(turn, [("X",x-Radio),("Y",y),("Z", z),("I",Radio), ("J",0)]))
		elif helicalCut == 	"Internal Right Thread" or helicalCut == "External Right Thread":
			block.append(CNC.gcode(turn, [("X",x-Radiox),("Y",y-Radioy),("Z", z),("I",Radio), ("J",0)]))

		elif helicalCut == 	"Internal Left Thread" or helicalCut ==	"External Left Thread":
			block.append(CNC.gcode(turn, [("X",x-Radiox),("Y",y+Radioy),("Z", z),("I",Radio), ("J",0)]))

		# Exit clearance 
		if helicalCut == "Internal Right Thread":
			block.append(CNC.gline(x-xsi,y-ysi))
		elif helicalCut == "Internal Left Thread":
			block.append(CNC.gline(x-xsi,y+ysi))
		if helicalCut == "External Right Thread":
			block.append(CNC.gline(x-xse,y-yse))
		elif helicalCut == "External Left Thread":
			block.append(CNC.gline(x-xse,y+yse))

		# Return to Z Safe
		if returnToSafeZ == 1: 
			if helicalCut == "Helical Cut" or helicalCut == "Internal Right Thread" or helicalCut == "Internal Left Thread":
				if entry == "Center":
					block.append(CNC.gline(x,y))
			block.append(CNC.zsafe())

		blocks.append(block)
		active = app.activeBlock()
		app.gcode.insBlocks(active, blocks, "Helical_Descent inserted")	#<<< insert blocks over active block in the editor
		app.refresh()												#<<< refresh editor
		app.setStatus(_("Generated: Helical_Descent Result"))				#<<< feed back result
