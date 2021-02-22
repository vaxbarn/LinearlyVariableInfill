# LinearlyVariableInfill
"""
Linearly Variable Infill for 3D prints.

Author: Barnabas Nemeth
Version: 1.5

"""

from ..Script import Script
from UM.Logger import Logger
from UM.Application import Application
import re #To perform the search
from cura.Settings.ExtruderManager import ExtruderManager
from collections import namedtuple
from enum import Enum
from typing import List, Tuple
from UM.Message import Message
from UM.i18n import i18nCatalog
catalog = i18nCatalog("cura")

__version__ = '1.5'

##-----------------------------------------------------------------------------------------------------------------------------------------------------------------

Point2D = namedtuple('Point2D', 'x y')
Segment = namedtuple('Segment', 'point1 point2')



class Infill(Enum):
    """Enum for infill type."""

    LINEAR = 1  # Linear infill like rectilinear or triangles

class Section(Enum):
    """Enum for section type."""

    NOTHING = 0
    INNER_WALL = 1
    OUTER_WALL = 2
    INFILL = 3


def dist(segment: Segment, point: Point2D) -> float:
    """Calculate the distance from a point to a line with finite length.

    Args:
        segment (Segment): line used for distance calculation
        point (Point2D): point used for distance calculation

    Returns:
        float: distance between ``segment`` and ``point``
    """
    px = segment.point2.x - segment.point1.x
    py = segment.point2.y - segment.point1.y
    norm = px * px + py * py
    u = ((point.x - segment.point1.x) * px + (point.y - segment.point1.y) * py) / float(norm)
    if u > 1:
        u = 1
    elif u < 0:
        u = 0
    x = segment.point1.x + u * px
    y = segment.point1.y + u * py
    dx = x - point.x
    dy = y - point.y

    return (dx * dx + dy * dy) ** 0.5


def two_points_distance(point1: Point2D, point2: Point2D) -> float:
    """Calculate the euclidean distance between two points.

    Args:
        point1 (Point2D): first point
        point2 (Point2D): second point

    Returns:
        float: euclidean distance between the points
    """
    return ((point1.x - point2.x) ** 2 + (point1.y - point2.y) ** 2) ** 0.5


def min_distance_to_segment(segment: Segment, segments: List[Segment]) -> float:
    """Calculate the minimum distance from the midpoint of ``segment`` to the nearest segment in ``segments``.

    Args:
        segment (Segment): segment to use for midpoint calculation
        segments (List[Segment]): segments list

    Returns:
        float: the smallest distance from the midpoint of ``segment`` to the nearest segment in the list
    """
    middlePoint = Point2D((segment.point1.x + segment.point2.x) / 2, (segment.point1.y + segment.point2.y) / 2)

    return min(dist(s, middlePoint) for s in segments)


def getXY(currentLineINcode: str) -> Point2D:
    """Create a ``Point2D`` object from a gcode line.

    Args:
        currentLineINcode (str): gcode line

    Raises:
        SyntaxError: when the regular expressions cannot find the relevant coordinates in the gcode

    Returns:
        Point2D: the parsed coordinates
    """
    searchX = re.search(r"X(\d*\.?\d*)", currentLineINcode)
    searchY = re.search(r"Y(\d*\.?\d*)", currentLineINcode)
    if searchX and searchY:
        elementX = searchX.group(1)
        elementY = searchY.group(1)
    else:
        raise SyntaxError('Gcode file parsing error for line {currentLineINcode}')

    return Point2D(float(elementX), float(elementY))


def mapRange(a: Tuple[float, float], b: Tuple[float, float], s: float) -> float:
    """Calculate a multiplier for the extrusion value from the distance to the perimeter.

    Args:
        a (Tuple[float, float]): a tuple containing:
            - a1 (float): the minimum distance to the perimeter (always zero at the moment)
            - a2 (float): the maximum distance to the perimeter where the interpolation is performed
        b (Tuple[float, float]): a tuple containing:
            - b1 (float): the maximum flow as a fraction
            - b2 (float): the minimum flow as a fraction
        s (float): the euclidean distance from the middle of a segment to the nearest perimeter

    Returns:
        float: a multiplier for the modified extrusion value
    """
    (a1, a2), (b1, b2) = a, b

    return b1 + ((s - a1) * (b2 - b1) / (a2 - a1))


def gcode_template(x: float, y: float, extrusion: float) -> str:
    """Format a gcode string from the X, Y coordinates and extrusion value.

    Args:
        x (float): X coordinate
        y (float): Y coordinate
        extrusion (float): Extrusion value

    Returns:
        str: Gcode line
    """
    return "G1 X{} Y{} E{}".format(round(x, 3), round(y, 3), round(extrusion, 5))


def is_layer(line: str) -> bool:
    """Check if current line is the start of a layer section.

    Args:
        line (str): Gcode line

    Returns:
        bool: True if the line is the start of a layer section
    """
    return line.startswith(";LAYER:")


def is_innerwall(line: str) -> bool:
    """Check if current line is the start of an inner wall section.

    Args:
        line (str): Gcode line

    Returns:
        bool: True if the line is the start of an inner wall section
    """
    return line.startswith(";TYPE:WALL-INNER")


def is_outerwall(line: str) -> bool:
    """Check if current line is the start of an outer wall section.

    Args:
        line (str): Gcode line

    Returns:
        bool: True if the line is the start of an outer wall section
    """
    return line.startswith(";TYPE:WALL-OUTER")


def ez_nyomtatasi_vonal(line: str) -> bool:
    """Check if current line is a standard printing segment.

    Args:
        line (str): Gcode line

    Returns:
        bool: True if the line is a standard printing segment
    """
    return "G1" in line and " X" in line and "Y" in line and "E" in line


def is_infill(line: str) -> bool:
    """Check if current line is the start of an infill.

    Args:
        line (str): Gcode line

    Returns:
        bool: True if the line is the start of an infill section
    """
    return line.startswith(";TYPE:FILL")


def fill_type(Mode):
    """Definie the type of Infill pattern

       Linearly Variable Infill like lineas or triangles = 1

    Args:
        line (Mode): Infill Pattern

    Returns:
        Int: the Type of infill pattern
    """
    iMode=0
    if Mode == 'grid':
        iMode=1
    if Mode == 'lines':
        iMode=1
    if Mode == 'triangles':
        iMode=1
    if Mode == 'trihexagon':
        iMode=1
    if Mode == 'cubic':
        iMode=1
    if Mode == 'cubicsubdiv':
        iMode=0
    if Mode == 'tetrahedral':
        iMode=1
    if Mode == 'quarter_cubic':
        iMode=1
    if Mode == 'concentric':
        iMode=0
    if Mode == 'zigzag':
        iMode=0
    if Mode == 'cross':
        iMode=0
    if Mode == 'cross_3d':
        iMode=0
    if Mode == 'gyroid':
        iMode=0

    return iMode
        
class LinearlyVariableInfill(Script):
    def getSettingDataString(self):
        return """{
            "name": "Linearly Variable Infill",
            "key": "LinearlyVariableInfill",
            "metadata": {},
            "version": 2,
            "settings":
            {
                "variableSegmentLength":
                {
                    "label": "Valtoztatott szakasz hossza",
                    "description": "Distance of the gradient (max to min) in mm",
                    "unit": "mm",
                    "type": "float",
                    "default_value": 6.0,
                    "minimum_value": 1.0,
                    "minimum_value_warning": 2.0
                },
                "divisionNR":
                {
                    "label": "Szakasz felosztasanak szama",
                    "description": "Only applicable for Linearly Variable Infills; number of segments within the gradient(fullSegmentLength=variableSegmentLength / divisionNR); use sensible values to not overload",
                    "type": "int",
                    "default_value": 4,
                    "minimum_value": 1,
                    "minimum_value_warning": 2
                },
   
                "variableSpeed":
                {
                    "label": "Valtozo sebesseg",
                    "description": "Activate also Valtozo sebesseg linked to the gradual flow",
                    "type": "bool",
                    "default_value": false
                },
                "maxSpeedFactor":
                {
                    "label": "Max sebesseg szorzo",
                    "description": "Maximum over speed factor",
                    "unit": "%",
                    "type": "int",
                    "default_value": 200,
                    "minimum_value": 100,
                    "maximum_value": 400,
                    "minimum_value_warning": 110,
                    "maximum_value_warning": 370,
                    "enabled": "variableSpeed"
                    
                },
                "minSpeedFactor":
                {
                    "label": "Min sebesseg szorzo",
                    "description": "Minimum over speed factor",
                    "unit": "%",
                    "type": "int",
                    "default_value": 60,
                    "minimum_value": 10,
                    "maximum_value": 100,
                    "minimum_value_warning": 40,
                    "maximum_value_warning": 90,
                    "enabled": "variableSpeed"
                    
                }, 
                "extruderNR":
                {
                    "label": "Extruder sorszam",
                    "description": "Define Extruder szam in case of multi extruders",
                    "unit": "",
                    "type": "int",
                    "default_value": 1
                
                }
            }
        }"""


## -----------------------------------------------------------------------------
#
#  Main Prog
#
## -----------------------------------------------------------------------------

    def execute(self, data):
        Logger.log('w', 'Plugin is starting '  )
        print('naygvera')
        division_nr = float(self.getSettingValueByKey("divisionNR"))
        variable_segment_lengh = float(self.getSettingValueByKey("variableSegmentLength"))
        extruder_nr  = self.getSettingValueByKey("extruderNR")
        extruder_nr = extruder_nr -1
        variable_speed= bool(self.getSettingValueByKey("variableSpeed"))
        max_speed_factor = float(self.getSettingValueByKey("maxSpeedFactor"))
        max_speed_factor = max_speed_factor /100
        min_speed_factor = float(self.getSettingValueByKey("minSpeedFactor"))
        min_speed_factor = min_speed_factor /100
        

        

        
        
        #   machine_extruder_count
     #   extruder_count=Application.getInstance().getGlobalContainerStack().getProperty("machine_extruder_count", "value")
      #  extruder_count = extruder_count-1
       # if extruder_nr>extruder_count :
        #    extruder_nr=extruder_count

        
        # Deprecation function
        extrud = list(Application.getInstance().getGlobalContainerStack().extruders.values())
        #extrud = Application.getInstance().getGlobalContainerStack().extruderList
        Message('Extrud:{}'.format(extrud), title = catalog.i18nc("@info:title", "Post Processing")).show()
        infillpattern = extrud[extruder_nr].getProperty("infill_pattern", "value")
        connectinfill = extrud[extruder_nr].getProperty("zig_zaggify_infill", "value")
        
        
        """Parse Gcode and modify infill portions with an extrusion width gradient."""
        currentSection = Section.NOTHING
        lastPosition = Point2D(-10000, -10000)
        littleSegmentLength = variable_segment_lengh / division_nr

        infill_type=fill_type(infillpattern)
        if infill_type == 0:
            #
            Logger.log('d', 'Infill Pattern not supported : ' + infillpattern)
            Message('Infill Pattern not supported : ' + infillpattern , title = catalog.i18nc("@info:title", "Post Processing")).show()

            return None

        if connectinfill == True:
            #
            Logger.log('d', 'Connect Infill Lines no supported')
            Message('Gcode must be generate without Connect Infill Lines mode activated' , title = catalog.i18nc("@info:title", "Post Processing")).show()
            return None      

        Logger.log('d',  "GradientFill Param : " + str(littleSegmentLength) + "/" + str(division_nr)+ "/" + str(variable_segment_lengh) ) #str(max_flow) + "/" + str(min_flow) + "/" + 
        Logger.log('d',  "Pattern Param : " + infillpattern + "/" + str(infill_type) )

        for layer in data:
            layer_index = data.index(layer)
            lines = layer.split("\n")
            for currentLineINcode in lines:
                new_Line=""
                stringFeed = ""
                line_index = lines.index(currentLineINcode)
                
                if is_layer(currentLineINcode):
                    perimeterSegments = []
                    
                if is_innerwall(currentLineINcode):
                    currentSection = Section.INNER_WALL
                    # Logger.log('d', 'is_innerwall'  )

                if is_outerwall(currentLineINcode):
                    currentSection = Section.OUTER_WALL
                    # Logger.log('d', 'is_outerwall' )
                    
                if currentSection == Section.INNER_WALL:
                    if ez_nyomtatasi_vonal(currentLineINcode):
                        Logger.log('d', 'Ez sor rossz ' + currentLineINcode)
                        perimeterSegments.append(Segment(getXY(currentLineINcode), lastPosition))
                    

                if is_infill(currentLineINcode):
                    # Log Size of perimeterSegments for debuging
                    Logger.log('d', 'PerimeterSegments seg : {}'.format(len(perimeterSegments)))
                    currentSection = Section.INFILL
                    # ! Important 
                    continue

                if currentSection == Section.INFILL:
                    if "F" in currentLineINcode and "G1" in currentLineINcode:
                        searchSpeed = re.search(r"F(\d*\.?\d*)", currentLineINcode)
                        
                        if searchSpeed:
                            current_speed=float(searchSpeed.group(1))
                            new_Line="G1 F{}\n".format(current_speed)
                        else:
                            Logger.log('d', 'Gcode file parsing error for line : ' + currentLineINcode )

                    if "E" in currentLineINcode and "G1" in currentLineINcode and "X" in currentLineINcode and "Y" in currentLineINcode:
                        currentPosition = getXY(currentLineINcode)
                        splitLine = currentLineINcode.split(" ")
                        
                        # ha lineraris  
                        if infill_type == 1:
                            for element in splitLine:
                                if "E" in element:
                                    E_inCode = float(element[1:])

                            fullSegmentLength = two_points_distance(lastPosition, currentPosition)
                            segmentSteps = fullSegmentLength / littleSegmentLength
                            extrudeLengthPERsegment = (0.006584 * fullSegmentLength) / segmentSteps
                            E_inCode_last = E_inCode - (extrudeLengthPERsegment * segmentSteps)
                            littlesegmentDirectionandLength = Point2D((currentPosition.x - lastPosition.x) / fullSegmentLength * littleSegmentLength,(currentPosition.y - lastPosition.y) / fullSegmentLength * littleSegmentLength)
                            speed_deficit = ((current_speed * max_speed_factor + current_speed * min_speed_factor) / division_nr)
                            step_number = 0
                            last_step_number = 0
    
    
    
    
                            if segmentSteps >= 2:
                                # new_Line=new_Line+"; LinearlyVariableInfill segmentSteps >= 2\n"
                                for step in range(int(segmentSteps)):
                                    segmentEnd = Point2D(lastPosition.x + littlesegmentDirectionandLength.x, lastPosition.y + littlesegmentDirectionandLength.y)
                                    extrudeLength=E_inCode_last+extrudeLengthPERsegment
                                    if perimeterSegments==[] : 
                                        Logger.log('d', 'Itt a hiba ' + currentLineINcode)
                                    shortestDistance = min_distance_to_segment(Segment(lastPosition, segmentEnd), perimeterSegments)
                                    if shortestDistance < variable_segment_lengh:
                                        segmentSpeed = current_speed 
    
                                        if variable_speed:
                                            if variable_speed:                                         
                                             
                                             if step_number < division_nr:                                              
                                                 segmentSpeed = current_speed * min_speed_factor + (speed_deficit * step_number)
  
                                             if step_number >= division_nr:                                            
                                                 segmentSpeed = current_speed * max_speed_factor
 
                                             if step_number >= segmentSteps - division_nr:                                                 
                                                 segmentSpeed = current_speed * max_speed_factor - (speed_deficit * last_step_number)
                                                 last_step_number=last_step_number + 1
                                            stringFeed = " F{}".format(int(segmentSpeed))

                                    else:
                                         segmentSpeed = current_speed * min_speed_factor
                                            
                                            
                                         if variable_speed:                                            
                                            if step_number < division_nr:                              
                                                 segmentSpeed = current_speed * min_speed_factor + (speed_deficit * step_number)
                                                 
                                            if step_number >= division_nr:                                                 
                                                 segmentSpeed = current_speed * max_speed_factor
                                                 

                                            if step_number >= segmentSteps - division_nr:                                             
                                                 segmentSpeed = current_speed * max_speed_factor - (speed_deficit * last_step_number)
                                                 last_step_number=last_step_number + 1

                                            stringFeed = " F{}".format(int(segmentSpeed))

                                    new_Line=new_Line + gcode_template(segmentEnd.x, segmentEnd.y, extrudeLength) + stringFeed + "\n" #szakaszExtrudalas
                                    lastPosition  = segmentEnd
                                    E_inCode_last = extrudeLength
                                    step_number = step_number + 1 
                                    
                    
                                segmentSpeed = current_speed * min_speed_factor
                                lastSpeed = " F{}".format(int(segmentSpeed))
                                new_Line=new_Line + gcode_template(currentPosition.x, currentPosition.y, E_inCode, ) + lastSpeed + "\n" #Original line for finish
                                lines[line_index] = new_Line
                                
                            else :
                                outPutLine = ""
                                # outPutLine = "; LinearlyVariableInfill segmentSteps < 2\n"
                               
                                for element in splitLine:
                                    if "E" in element:
                                        outPutLine = outPutLine + "E" + str(round(E_inCode, 5))
                                    else:
                                        outPutLine = outPutLine + element + " "
                                outPutLine = outPutLine # + "\n"
                                lines[line_index] = outPutLine
                                
                            # writtenToFile = 1
                            
                 
                    #
                    # comment like ;MESH:NONMESH 
                    #
                    if ";" in currentLineINcode:
                        currentSection = Section.NOTHING
                        lines[line_index] = currentLineINcode # other Comment 
                #
                # line with move
                #
                if "X" in currentLineINcode and "Y" in currentLineINcode and ("G1" in currentLineINcode or "G0" in currentLineINcode):
                    lastPosition  = getXY(currentLineINcode)

            final_lines = "\n".join(lines)
            data[layer_index] = final_lines
        return data
