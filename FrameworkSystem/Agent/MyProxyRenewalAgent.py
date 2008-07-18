########################################################################
# $Header: /tmp/libdirac/tmp.stZoy15380/dirac/DIRAC3/DIRAC/FrameworkSystem/Agent/MyProxyRenewalAgent.py,v 1.4 2008/07/18 11:06:15 acasajus Exp $
########################################################################

"""  Proxy Renewal agent is the key element of the Proxy Repository
     which maintains the user proxies alive
"""

from DIRAC.Core.Base.Agent import Agent
from DIRAC  import gLogger, gConfig, S_OK, S_ERROR
from DIRAC.FrameworkSystem.DB.ProxyDB import ProxyDB
from DIRAC.Core.Utilities.ThreadPool import ThreadPool

AGENT_NAME = 'Framework/MyProxyRenewalAgent'

class MyProxyRenewalAgent(Agent):

  def __init__(self):
    """ Standard constructor
    """
    Agent.__init__( self, AGENT_NAME, initializeMonitor = True )

  def initialize(self):


    requiredLifeTime = gConfig.getValue( "%s/MinimumLifeTime" % self.section, 3600 )
    renewedLifeTime = gConfig.getValue( "%s/RenewedLifeTime" % self.section, 54000 )
    myProxyServer = gConfig.getValue( "/DIRAC/VOPolicy/MyProxyServer" , "myproxy.cern.ch" )
    self.proxyDB = ProxyDB( requireVoms = True,
                            useMyProxy = True
                          )

    gLogger.info( "Minimum Life time      : %s" % requiredLifeTime )
    gLogger.info( "Life time on renew     : %s" % renewedLifeTime )
    gLogger.info( "MyProxy server         : %s" % self.proxyDB.getMyProxyServer() )
    gLogger.info( "MyProxy max proxy time : %s" % self.proxyDB.getMyProxyMaxLifeTime() )

    self.__threadPool = ThreadPool( 1, 10 )
    Agent.initialize( self )
    return S_OK()

  def __renewProxyForCredentials( self, userDN, userGroup ):
    lifeTime = gConfig.getValue( "%s/RenewedLifeTime" % self.section, 54000 )
    gLogger.info( "Renewing for %s@%s %s secs" % ( userDN, userGroup, lifeTime ) )
    retVal = self.proxyDB.renewFromMyProxy( userDN,
                                            userGroup,
                                            lifeTime = lifeTime )
    if not retVal[ 'OK' ]:
      gLogger.error( "Failed to renew for %s@%s : %s" %( userDN, userGroup, retVal[ 'Message' ] ) )
    else:
      gLogger.info( "Renewed proxy for %s@%s" % ( userDN, userGroup ) )

  def __treatRenewalCallback( self, oTJ, exceptionList ):
    gLogger.exception( lException = exceptionList )

  def execute(self):
    """ The main agent execution method
    """
    self.proxyDB.purgeLogs()
    gLogger.info( "Purging expired requests" )
    retVal = self.proxyDB.purgeExpiredRequests()
    if retVal[ 'OK' ]:
      gLogger.info( " purged %s requests" % retVal[ 'Value' ] )
    gLogger.info( "Purging expired proxies" )
    retVal = self.proxyDB.purgeExpiredProxies()
    if retVal[ 'OK' ]:
      gLogger.info( " purged %s proxies" % retVal[ 'Value' ] )
    retVal = self.proxyDB.getCredentialsAboutToExpire( gConfig.getValue( "%s/MinimumLifeTime" % self.section, 3600 ) )
    if not retVal[ 'OK' ]:
      return retVal
    data = retVal[ 'Value' ]
    gLogger.info( "Renewing %s proxies..." % len( data ) )
    for record in data:
      userDN = record[0]
      userGroup = record[1]
      self.__threadPool.generateJobAndQueueIt( self.__renewProxyForCredentials,
                                               args = ( userDN, userGroup ),
                                               oExceptionCallback = self.__treatRenewalCallback )
    self.__threadPool.processAllResults()
    return S_OK()
