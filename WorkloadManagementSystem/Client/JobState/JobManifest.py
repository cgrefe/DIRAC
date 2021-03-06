
from DIRAC import S_OK, S_ERROR, gConfig
from DIRAC.ConfigurationSystem.Client.PathFinder import getAgentSection
from DIRAC.Core.Utilities.CFG import CFG
from DIRAC.Core.Utilities import List
from DIRAC.ConfigurationSystem.Client.Helpers.Operations import Operations
from DIRAC.Core.Utilities.JDL import loadJDLAsCFG, dumpCFGAsJDL

class JobManifest( object ):

  def __init__( self, manifest = "" ):
    self.__manifest = CFG()
    self.__dirty = False
    if manifest:
      result = self.loadManifest( manifest )
      if not result[ 'OK' ]:
        raise Exception( result[ 'Message' ] )

  def isDirty( self ):
    return self.__dirty

  def setDirty( self ):
    self.__dirty = True

  def clearDirty( self ):
    self.__dirty = False

  def load( self, dataString ):
    """
    Auto discover format type based on [ .. ] of JDL
    """
    dataString = dataString.strip()
    if dataString[0] == "[" and dataString[-1] == "]":
      return self.loadJDL( dataString )
    else:
      return self.loadCFG( dataString )

  def loadJDL( self, jdlString ):
    """
    Load job manifest from JDL format
    """
    result = loadJDLAsCFG( jdlString.strip() )
    if not result[ 'OK' ]:
      self.__manifest = CFG()
      return result
    self.__manifest = result[ 'Value' ][0]
    return S_OK()

  def loadCFG( self, cfgString ):
    """
    Load job manifest from CFG format
    """
    try:
      self.__manifest.loadFromBuffer( cfgString )
    except Exception, e:
      return S_ERROR( "Can't load manifest from cfg: %s" % str( e ) )
    return S_OK()

  def dumpAsCFG( self ):
    return str( self.__manifest )

  def getAsCFG( self ):
    return self.__manifest.copy()

  def dumpAsJDL( self ):
    return dumpCFGAsJDL( self.__manifest )

  def __checkNumericalVar( self, varName, defaultVal, minVal, maxVal ):
    """
    Check a numerical var
    """
    initialVal = False
    if varName not in self.__manifest:
      varValue = gConfig.getValue( "/JobManifest/Default%s" % varName , defaultVal )
    else:
      varValue = self.__manifest[ varName ]
      initialVal = varValue
    try:
      varValue = long( varValue )
    except:
      return S_ERROR( "%s must be a number" % varName )
    minVal = gConfig.getValue( "/JobManifest/Min%s" % varName, minVal )
    maxVal = gConfig.getValue( "/JobManifest/Max%s" % varName, maxVal )
    varValue = max( minVal, min( varValue, maxVal ) )
    if initialVal != varValue:
      self.__manifest.setOption( varName, varValue )
    return S_OK( varValue )

  def __checkChoiceVar( self, varName, defaultVal, choices ):
    """
    Check a choice var
    """
    initialVal = False
    if varName not in self.__manifest:
      varValue = gConfig.getValue( "/JobManifest/Default%s" % varName , defaultVal )
    else:
      varValue = self.__manifest[ varName ]
      initialVal = varValue
    if varValue not in gConfig.getValue( "/JobManifest/Choices%s" % varName , choices ):
      return S_ERROR( "%s is not a valid value for %s" % ( varValue, varName ) )
    if initialVal != varValue:
      self.__manifest.setOption( varName, varValue )
    return S_OK( varValue )

  def __checkMultiChoice( self, varName, choices ):
    """
    Check a multi choice var
    """
    initialVal = False
    if varName not in self.__manifest:
      return S_OK()
    else:
      varValue = self.__manifest[ varName ]
      initialVal = varValue
    choices = gConfig.getValue( "/JobManifest/Choices%s" % varName , choices )
    for v in List.fromChar( varValue ):
      if v not in choices:
        return S_ERROR( "%s is not a valid value for %s" % ( v, varName ) )
    if initialVal != varValue:
      self.__manifest.setOption( varName, varValue )
    return S_OK( varValue )

  def __checkMaxInputData( self, maxNumber ):
    """
    Check Maximum Number of Input Data files allowed
    """
    initialVal = False
    varName = "InputData"
    if varName not in self.__manifest:
      return S_OK()
    varValue = self.__manifest[ varName ]
    if len( List.fromChar( varValue ) ) > maxNumber:
      return S_ERROR( 'Number of Input Data Files (%s) greater than current limit: %s' % ( len( List.fromChar( varValue ) ) , maxNumber ) )
    return S_OK()


  def __contains__( self, key ):
    """ Check if the manifest has the required key
    """
    return key in self.__manifest

  def setOptionsFromDict( self, varDict ):
    for k in sorted( varDict ):
      self.setOption( k, varDict[ k ] )

  def check( self ):
    """
    Check that the manifest is OK
    """
    for k in [ 'OwnerName', 'OwnerDN', 'OwnerGroup', 'DIRACSetup' ]:
      if k not in self.__manifest:
        return S_ERROR( "Missing var %s in manifest" % k )
    #Check CPUTime
    result = self.__checkNumericalVar( "CPUTime", 86400, 0, 500000 )
    if not result[ 'OK' ]:
      return result
    result = self.__checkNumericalVar( "Priority", 1, 0, 10 )
    if not result[ 'OK' ]:
      return result
    allowedSubmitPools = []
    for option in [ "DefaultSubmitPools", "SubmitPools", "AllowedSubmitPools" ]:
      allowedSubmitPools = gConfig.getValue( "%s/%s" % ( getAgentSection( "WorkloadManagement/TaskQueueDirector" ), option ),
                                             allowedSubmitPools )
    result = self.__checkMultiChoice( "SubmitPools", allowedSubmitPools )
    if not result[ 'OK' ]:
      return result
    result = self.__checkMultiChoice( "PilotTypes", [ 'private' ] )
    if not result[ 'OK' ]:
      return result
    result = self.__checkMaxInputData( 500 )
    if not result[ 'OK' ]:
      return result
    result = self.__checkMultiChoice( "JobType", Operations().getValue( "JobDescription/AllowedJobTypes", [] ) )
    if not result[ 'OK' ]:
      return result
    return S_OK()

  def createSection( self, secName, contents = False ):
    if secName not in self.__manifest:
      if contents and not isinstance( contents, CFG ):
        return S_ERROR( "Contents for section %s is not a cfg object" % secName )
      self.__dirty = True
      S_OK( self.__manifest.createSection( secName, contents = contents ) )
    return S_ERROR( "Section %s already exists" % secName )

  def getSection( self, secName ):
    self.__dirty = True
    sec = self.__manifest[ secName ]
    if not sec:
      return S_ERROR( "%s does not exist" )
    return S_OK( sec )


  def setSectionContents( self, secName, contents ):
    if contents and not isinstance( contents, CFG ):
      return S_ERROR( "Contents for section %s is not a cfg object" % secName )
    self.__dirty = True
    if secName in self.__manifest:
      self.__manifest[ secName ].reset()
      self.__manifest[ secName ].mergeWith( contents )
    else:
      self.__manifest.createNewSection( secName, contents = contents )

  def setOption( self, varName, varValue ):
    """
    Set a var in job manifest
    """
    self.__dirty = True
    levels = List.fromChar( varName, "/" )
    cfg = self.__manifest
    for l in levels[:-1]:
      if l not in cfg:
        cfg.createNewSection( l )
      cfg = cfg[ l ]
    cfg.setOption( levels[-1], varValue )

  def removeOption( self, opName ):
    levels = List.fromChar( opName, "/" )
    cfg = self.__manifest
    for l in levels[:-1]:
      if l not in cfg:
        return S_ERROR( "%s does not exist" % opName )
      cfg = cfg[ l ]
    if cfg.deleteKey( levels[ -1 ] ):
      self.__dirty = True
      return S_OK()
    return S_ERROR( "%s does not exist" % opName )

  def getOption( self, varName, defaultValue = None ):
    """
     Get a variable from the job manifest
    """
    cfg = self.__manifest
    return cfg.getOption( varName, defaultValue )

  def getOptionList( self, section = "" ):
    """
    Get a list of variables in a section of the job manifest
    """
    cfg = self.__manifest.getRecursive( section )
    if not cfg or 'value' not in cfg:
      return []
    cfg = cfg[ 'value' ]
    return cfg.listOptions()

  def getSectionList( self, section = "" ):
    """
    Get a list of sections in the job manifest
    """
    cfg = self.__manifest.getRecursive( section )
    if not cfg or 'value' not in cfg:
      return []
    cfg = cfg[ 'value' ]
    return cfg.listSections()
