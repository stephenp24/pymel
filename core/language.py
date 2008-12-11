"""
Functions and classes related to scripting, including `MelGlobals` and `Mel`
"""
from math import *
from pymel.util.mathutils import *
import system
import pymel.util as util
import maya.mel as mm
import pmcmds as cmds
#import maya.cmds as cmds
from pymel.mayahook.optionvars import *
import os, inspect
import factories as _factories
import pymel.api as api
import pmtypes as _types

#--------------------------
# Mel <---> Python Glue
#--------------------------  

MELTYPES = ['string', 'string[]', 'int', 'int[]', 'float', 'float[]', 'vector', 'vector[]']

def isValidMelType( typStr ):
    """:rtype: bool"""
    return typStr in MELTYPES

def pythonToMel(arg):
    """convert a python object to a string representing an equivalent value in mel"""
    if util.isNumeric(arg):
        return str(arg)
    if util.isIterable(arg):
        return '{%s}' % ','.join( map( pythonToMel, arg) )
    
    # in order for PyNodes to get wrapped in quotes we have to treat special cases first,
    # we cannot simply test if arg is an instance of basestring because PyNodes are not  
    return '"%s"' % cmds.encodeString(str(arg))


def getMelType( pyObj, exactOnly=True, allowBool=False, allowMatrix=False ):
    """return the name of the closest mel type equivalent for the given python object. 
    mel has no true boolean or matrix types, but it often reserves special treatment for them in other ways.
    To control the handling of these types, use `allowBool` and `allowMatrix`. 
    For python iterables, the first element in the array is used to determine the type. for empty lists, 'string[]' is
    returned.
    
    :Parameters:
        pyObj
            can be either a class or an instance.
        exactOnly : bool
            If True and no suitable mel analog can be found, the function will return None.
            If False, types which do not have an exact mel analog will return the python type name as a string
        allowBool : bool
            if True and a bool type is passed, 'bool' will be returned. otherwise 'int'.
        allowMatrix : bool
             if True and a `Matrix` type is passed, 'matrix' will be returned. otherwise 'int[]'.
    
    :rtype: str
    
        >>> from pymel import *
        >>> getMelType( 1 )
        'int'
        >>> p = SCENE.persp
        >>> getMelType( p.translate.get() )
        'vector'
        >>> getMelType( Matrix )
        'int[]'
        >>> getMelType( Matrix, allowMatrix=True )
        'matrix'
        >>> getMelType( True )
        'int'
        >>> getMelType( True, allowBool=True)
        'bool'
        >>> # make a dummy class
        >>> class MyClass(object): pass
        >>> getMelType( MyClass )
        None
        >>> getMelType( MyClass, exactOnly=False )
        'MyClass'
    
    """
 
    if inspect.isclass(pyObj):

        if issubclass( pyObj, basestring ) : return 'string'
        elif allowBool and issubclass( pyObj, bool ) : return 'bool'
        elif issubclass( pyObj, int ) : return 'int'
        elif issubclass( pyObj, float ) : return 'float'         
        elif issubclass( pyObj, _types.VectorN ) : return 'vector'
        elif issubclass( pyObj, _types.MatrixN ) : 
            if allowMatrix: 
                return 'matrix'
            else:
                return 'int[]'
            
        elif not exactOnly:
            return pyObj.__name__
            
    else:

        if isIterable( pyObj ):
            try:
                return getMelType( pyObj=arg[0], exactOnly=True ) + '[]'
            except IndexError:
                # TODO : raise warning
                return 'string[]'
            except:
                return
        if isinstance( pyObj, basestring ) : return 'string'
        elif allowBool and isinstance( pyObj, bool ) : return 'bool'
        elif isinstance( pyObj, int ) : return 'int'
        elif isinstance( pyObj, float ) : return 'float'         
        elif isinstance( pyObj, _types.VectorN ) : return 'vector'
        elif isinstance( pyObj, _types.MatrixN ) : 
            if allowMatrix: 
                return 'matrix'
            else:
                return 'int[]'
            
        elif not exactOnly:
            typeStr = type(pyObj).__name__

         
# TODO : convert array variables to a semi-read-only list ( no append or extend, += is ok ): 
# using append or extend will not update the mel variable 
class MelGlobals( dict ):
    """ A dictionary-like class for getting and setting global variables between mel and python.
    an instance of the class is created by default in the pymel namespace as melGlobals.
    
    to retrieve existing global variables, just use the name as a key
    
    >>> melGlobals['gMainFileMenu']
    mainFileMenu
    >>> # works with or without $
    >>> melGlobals['$gGridDisplayGridLinesDefault']
    1
    
    creating new variables requires the use of the initVar function to specify the type
    
    >>> melGlobals.initVar( 'string', 'gMyStrVar' )
    >>> melGlobals['gMyStrVar'] = 'fooey'
    
    """
    __metaclass__ = util.Singleton
    melTypeToPythonType = {
        'string'    : str,
        'int'       : int,
        'float'     : float,
        'vector'    : _types.Vector
        }

#    class MelGlobalArray1( tuple ):
#        def __new__(cls, type, variable, *args, **kwargs ): 
#             
#            self = tuple.__new__( cls, *args, **kwargs )
#            
#            decl_name = variable
#            if type.endswith('[]'):
#                type = type[:-2]
#                decl_name += '[]'
#                
#            self._setItemCmd = "global %s %s; %s" % ( type, decl_name, variable )
#            self._setItemCmd += '[%s]=%s;'
#            return self
#        
#        def setItem(self, index, value ):
#            mm.eval(self._setItemCmd % (index, value) )

    class MelGlobalArray( util.defaultlist ):
        #__metaclass__ = util.metaStatic
        def __init__(self, type, variable, *args, **kwargs ): 
            
            decl_name = variable
            if type.endswith('[]'):
                type = type[:-2]
                decl_name += '[]'
            
            pyType = MelGlobals.melTypeToPythonType[ type ]
            util.defaultlist.__init__( self, pyType, *args, **kwargs )
             
               
            self._setItemCmd = "global %s %s; %s" % ( type, decl_name, variable )
            self._setItemCmd += '[%s]=%s;'

        
        def setItem(self, index, value ):
            mm.eval(self._setItemCmd % (index, value) )
        
        # prevent these from 
        def append(self, val): raise AttributeError
        def __setitem__(self, item, val): raise AttributeError
        def extend(self, val): raise AttributeError
        
    
    
    typeMap = {}
    validTypes = MELTYPES

    
    def __getitem__(self, variable ):
        return self.__class__.get( variable )
    
    def __setitem__(self, variable, value):
        return self.__class__.set( variable, value )

    @classmethod
    def _formatVariable(cls, variable):
        # TODO : add validity check
        if not variable.startswith( '$'):
            variable = '$' + variable
        return variable
    
    @classmethod
    def getType(cls, variable):
        variable = cls._formatVariable(variable)
        info = mel.whatIs( variable ).split()
        if len(info)==2 and info[1] == 'variable':
            return info[0]
        raise TypeError, "Cannot determine type for this variable. Use melGlobals.initVar first."
      
    @classmethod   
    def initVar( cls, type, variable ):
        if type not in MelGlobals.validTypes:
            raise TypeError, "type must be a valid mel type: %s" % ', '.join( [ "'%s'" % x for x in MelGlobals.validTypes ] )
        variable = cls._formatVariable(variable)
        MelGlobals.typeMap[variable] = type
        return variable
    
    @classmethod
    def get( cls, variable, type=None  ):
        """get a MEL global variable.  If the type is not specified, the mel ``whatIs`` command will be used
        to determine it.""" 
        
        variable = cls._formatVariable(variable)
        if type is None:
            try:
                type = MelGlobals.typeMap[variable]
            except KeyError:
                type = cls.getType(variable)
            
        variable = cls.initVar(type, variable)
        
        ret_type = type
        decl_name = variable
        
        if type.endswith('[]'):
            array=True
            type = type[:-2]
            proc_name = 'pymel_get_global_' + type + 'Array'
            if not decl_name.endswith('[]'):
                decl_name += '[]'
        else:
            array=False
            proc_name = 'pymel_get_global_' + type
            
        cmd = "global proc %s %s() { global %s %s; return %s; } %s();" % (ret_type, proc_name, type, decl_name, variable, proc_name )
        #print cmd
        res = mm.eval( cmd  )
        if array:
            return MelGlobals.MelGlobalArray(ret_type, variable, res)
        else:
            return res
    
    @classmethod
    def set( cls, variable, value, type=None ):
        """set a mel global variable""" 
        variable = cls._formatVariable(variable)
        if type is None:
            try:
                type = MelGlobals.typeMap[variable]
            except KeyError:
                type = cls.getType(variable)
                
        variable = cls.initVar(type, variable)
        decl_name = variable
        if type.endswith('[]'):
            type = type[:-2]
            decl_name += '[]'
            
        cmd = "global %s %s; %s=%s;" % ( type, decl_name, variable, pythonToMel(value) )
        #print cmd
        mm.eval( cmd  )
    
    @classmethod
    def keys(cls):
        """list all global variables"""
        return mel.env()
    
melGlobals = MelGlobals()

# for backward compatibility               
def getMelGlobal(type, variable) :
    return melGlobals.get(variable, type)
def setMelGlobal(type, variable, value) :
    return melGlobals.set(variable, value, type)

    
class Catch(object):
    """Reproduces the behavior of the mel command of the same name. if writing pymel scripts from scratch, you should
        use the try/except structure. This command is provided for python scripts generated by py2mel.  stores the
        result of the function in catch.result.
        
        >>> if not catch( lambda: myFunc( "somearg" ) ):
        >>>    result = catch.result
        >>>    print "succeeded:", result
        
        """
    __metaclass__ = util.Singleton
    result = None
    success = None
    def __call__(self, func ):
        try:
            Catch.result = func()
            Catch.success = True
            return 0
        except:
            Catch.success = False
            return 1
        
    def reset(self):
        Catch.result = None
        Catch.success = None 

catch = Catch()
             
#--------------------------
# Maya.mel Wrapper
#--------------------------

class MelError(RuntimeError):
    """Generic MEL error"""
    pass

class MelConversionError(MelError,TypeError):
    """Error raised when MEL cannot process a conversion or cast between data types"""
    pass

class UnknownMelProcedure(MelError,NameError):
    """The called mel procedure does not exist or has not been sourced"""
    pass

class MelArgumentError(MelError,TypeError):
    """The arguments passed to the mel script are incorrect"""
    pass

class Mel(object):
    """This class is a convenience for calling mel scripts from python, but if you are like me, you'll quickly find that it
    is a necessity. It allows mel scripts to be called as if they were python functions: it automatically formats python
    arguments into a command string which is executed via maya.mel.eval.  An instance of this class is already created for you 
    when importing pymel and is called `mel`.  
    
    
        
    default:        
        >>> import maya.mel as mel
        >>> # create the proc
        >>> mel.eval( 'global proc myScript( string $stringArg, float $floatArray[] ){}')
        >>> # run the script
        >>> mel.eval( 'myScript("firstArg", {1.0, 2.0, 3.0})')
            
    pymel:
        >>> from pymel import *
        >>> # create the proc
        >>> mel.eval( 'global proc myScript( string $stringArg, float $floatArray[] ){}')
        >>> # run the script
        >>> mel.myScript("firstArg", [1.0, 2.0, 3.0])
        
    The above is a very simplistic example. The advantages of pymel.mel over maya.mel.eval are more readily
    apparent when we want to pass a python object to our mel procedure:
    
    default:        
        >>> import cmds as cmds
        >>> node = "lambert1"
        >>> color = cmds.getAttr( node + ".color" )[0]
        >>> mel.eval('myScript("%s",{%f,%f,%f})' % (cmds.nodeType(node), color[0], color[1], color[2])    
            
    pymel:
        >>> from pymel import *
        >>> node = PyNode("lambert1")
        >>> mel.myScript( node.type(), node.color.get() )
    
    In this you can see how `pymel.core.mel` allows you to pass any python object directly to your mel script as if 
    it were a python function, with no need for formatting arguments.  The resulting code is much more readable.
    
    Another advantage of this class over maya.mel.eval is its handling of mel errors.  If a mel procedure fails to
    execute, you will get the specific mel error message in the python traceback, and, if they are enabled, line numbers!
    
    For example, in the example below we redeclare the myScript procedure with a line that will result in an error:
    
        >>> mel.eval( '''global proc myScript( string $stringArg, float $floatArray[] ){ 
        ...     float $donuts = `ls -type camera`;}''')
        >>> mel.myScript( 'foo', [] )
        Error: line 2: Cannot convert data of type string[] to type float.
        Traceback (most recent call last):
            ...
        pymel.core.language.MelConversionError: Error occurred during execution of MEL script: line 2: Cannot convert data of type string[] to type float.

    
    Notice that the error raised is a `MelConversionError`.  There are several MEL exceptions that may be raised,
    depending on the type of error: `MelError`, `MelConversionError`, `MelArgumentError`, and `UnknownProcedureError`.
    To remain backward compatible with maya.cmds and older versions of pymel, all MEL exceptions inherit from 
    `MelError`, which in turn inherits from `RuntimeError`.
    
    
    """
          
    def __getattr__(self, command):
        if command.startswith('__') and command.endswith('__'):
            return self.__dict__[command]
        def _call(*args, **kwargs):
        
            strArgs = [pythonToMel(arg) for arg in args]
            
            if kwargs:
                strFlags = [ '-%s %s' % ( key, pythonToMel(val) ) for key, val in kwargs.items() ]
                cmd = '%s %s %s' % ( command, ' '.join( strFlags ), ' '.join( strArgs ) )
                
            else:
                cmd = '%s(%s)' % ( command, ','.join( strArgs ) )
            
            return self.eval(cmd)
            #print cmd
#            try:
#                return mm.eval(cmd)
#            except RuntimeError, msg:
#                info = self.whatIs( command )
#                if info.startswith( 'Presumed Mel procedure'):
#                    raise NameError, 'Unknown Mel procedure'
#                raise RuntimeError, "%s: %s" % ( msg, cmd )

        return _call
    

    @staticmethod
    def mprint(self, *args):
        """mel print command in case the python print command doesn't cut it. i have noticed that python print does not appear
        in certain output, such as the rush render-queue manager."""
        #print r"""print (%s\\n);""" % pythonToMel( ' '.join( map( str, args))) 
        mm.eval( r"""print (%s);""" % pythonToMel( ' '.join( map( str, args))) + '\n' )
    
    @classmethod
    def source( cls, script, language='mel' ):
        """use this to source mel or python scripts.
        language : 'mel', 'python'
            When set to 'python', the source command will look for the python equivalent of this mel file, if
            it exists, and attempt to import it. This is particularly useful when transitioning from mel to python
            via mel2py, with this simple switch you can change back and forth from sourcing mel to importing python.
            
        """
        
        if language == 'mel':
            cls.eval( """source "%s";""" % script )
            
        elif language == 'python':
            script = _path.path( script )
            modulePath = script.namebase
            folder = script.parent
            print modulePath
            if not sys.modules.has_key(modulePath):
                print "importing"
                module = __import__(modulePath, globals(), locals(), [''])
                sys.modules[modulePath] = module
            
        else:
            raise TypeError, "language keyword expects 'mel' or 'python'. got '%s'" % language
    
    @staticmethod        
    def eval( cmd ):
        """
        evaluate a string as a mel command and return the result. 
        
        Behaves like maya.mel.eval, with several improvments:
            - returns pymel `Vector` and `Matrix` classes
            - when an error is encountered a `MelError` exception is raised, along with the line number (if enabled) and exact mel error.
        
        >>> mel.eval( 'attributeExists("persp", "translate")' )
        0
        >>> mel.eval( 'interToUI( "fooBarSpangle" )' )
        u'Foo Bar Spangle'
        
        """
        # should return a value, like mm.eval
        #return mm.eval( cmd )   
        # get this before installing the callback
        undoState = cmds.undoInfo(q=1, state=1)
         
        global errors
        errors = []
        def errorCallback( nativeMsg, messageType, data ):
            global errors
            if messageType == api.MCommandMessage.kError:
                if nativeMsg:
                    errors +=  [ nativeMsg ]
        
        # setup the callback:
        # assigning ids to a list avoids the swig memory leak warning, which would scare a lot of people even though 
        # it is harmless.  hoping we get a real solution to this so that we don't have to needlessly accumulate this data
        id = api.MCommandMessage.addCommandOutputCallback( errorCallback, None ) 
        
        
        try:
            res = api.MCommandResult()
            api.MGlobal.executeCommand( cmd, res, False, undoState )
        except:
            # these two lines would go in a finally block, but we have to maintain python 2.4 compatibility for maya 8.5
            api.MMessage.removeCallback( id )
            id.disown()
            msg = '\n'.join( errors)
            if 'Cannot find procedure' in msg:
                e = UnknownMelProcedure
            elif 'Wrong number of arguments' in msg:
                e = MelArgumentError
            elif 'Cannot convert data' in msg or 'Cannot cast data' in msg:
                e = MelConversionError
            else:
                e = MelError
            raise e, "Error occurred during execution of MEL script: %s" % ( msg )
        else:   
            # these two lines would go in a finally block, but we have to maintain python 2.4 compatibility for maya 8.5
            api.MMessage.removeCallback( id )
            id.disown()
            
            resType = res.resultType()
            
            if resType == api.MCommandResult.kInvalid:
                return   
            elif resType == api.MCommandResult.kInt:
                result = api.MScriptUtil().asIntPtr()
                res.getResult(result)
                return api.MScriptUtil(result).asInt()
            elif resType == api.MCommandResult.kIntArray:
                result = api.MIntArray()
                res.getResult(result)
                return [ result[i] for i in range( result.length() ) ]
            elif resType == api.MCommandResult.kDouble:
                result = api.MScriptUtil().asDoublePtr()
                res.getResult(result)
                return api.MScriptUtil(result).asDouble()
            elif resType == api.MCommandResult.kDoubleArray:
                result = api.MDoubleArray()
                res.getResult(result)
                return [ result[i] for i in range( result.length() ) ]
            elif resType == api.MCommandResult.kString:
                return res.stringResult()
            elif resType == api.MCommandResult.kStringArray:
                result = []
                res.getResult(result)
                return result
            elif resType == api.MCommandResult.kVector:
                result = api.MVector()
                res.getResult(result)
                return _types.Vector(result)    
            elif resType == api.MCommandResult.kVectorArray:
                result = api.MMatrixArray()
                res.getResult(result)
                return [ _types.Vector(result[i]) for i in range( result.length() ) ]
            elif resType == api.MCommandResult.kMatrix:
                result = api.MMatrix()
                res.getResult(result)
                return _types.Matrix(result)   
            elif resType == api.MCommandResult.kMatrixArray:
                result = api.MMatrixArray()
                res.getResult(result)
                return [ _types.Matrix(result[i]) for i in range( result.length() ) ]
             
    @staticmethod   
    def error( msg, showLineNumber=False ):       
        if showLineNumber:
            flags = ' -showLineNumber true '
        else:
            flags = ''
        mm.eval( """error %s %s""" % ( flags, pythonToMel( msg) ) )

    @staticmethod
    def warning( msg, showLineNumber=False ):       
        if showLineNumber:
            flags = ' -showLineNumber true '
        else:
            flags = ''
        mm.eval( """warning %s %s""" % ( flags, pythonToMel( msg) ) )

    @staticmethod
    def trace( msg, showLineNumber=False ):       
        if showLineNumber:
            flags = ' -showLineNumber true '
        else:
            flags = ''
        mm.eval( """trace %s %s""" % ( flags, pythonToMel( msg) ) )
    
    @staticmethod
    def tokenize( *args ):
        raise NotImplementedError, "Calling the mel command 'tokenize' from python will crash Maya. Use the string split method instead."

mel = Mel()


def conditionExists(conditionName):
	"""
	Returns True if the named condition exists, False otherwise.
	
	Note that 'condition' here refers to the type used by 'isTrue' and 'scriptJob', NOT to the condition NODE.
	"""
	return conditionName in cmds.scriptJob(listConditions=True)
	

class MayaGlobals(object):
    """
    A Singleton class to represent Maya current optionVars and settings which are global
    to all of maya and are not saved with the scene.
    """
    __metaclass__ = util.Singleton
    
    optionVars = OptionVarDict()
    #grid = Grid()
    #playbackOptions = PlaybackOptions()
    
    # TODO : create a wrapper for os.environ which allows direct appending and popping of individual env entries (i.e. make ':' transparent)
    envVars = os.environ
    @staticmethod
    def setConstructionHistory( state ):
        cmds.constructionHistory( tgl=state )
    @staticmethod
    def getConstructionHistory(self):
        return cmds.constructionHistory( q=True, tgl=True )

    @staticmethod
    def setUpAxis( axis, rotateView=False ):
        """This flag specifies the axis as the world up direction. The valid axis are either 'y' or 'z'."""
        cmds.upAxis( axis=axis.lower(), rotateView=rotateView )
    
    @staticmethod
    def getUpAxis(self):
        """This flag gets the axis set as the world up direction. The valid axis are either 'y' or 'z'."""
        return cmds.upAxis( q=True, axis=True )    

    @staticmethod
    def user():
        return getuser() 
    
    @staticmethod   
    def host():
        return gethostname()
    
    
class SceneGlobals(object):
    """
    A Static Singleton class to represent scene-dependent settings.
    """
    __metaclass__ = util.Singleton
    
    @staticmethod
    def sceneName():
        return system.Path(cmds.file( q=1, sn=1))

    @util.universalmethod
    def getTime(obj):
        return cmds.currentTime( q=1 )
    
    @util.universalmethod
    def setTime( obj, val ):
        cmds.currentTime( val )    
    time = property( getTime, setTime )
    
    @staticmethod
    def getMinTime():
        return cmds.playbackOptions( q=1, minTime=1 )
    @staticmethod
    def setMinTime( val ):
        cmds.playbackOptions( minTime=val )
    minTime = property( getMinTime, setMinTime )

    @staticmethod
    def getMaxTime():
        return cmds.playbackOptions( q=1, maxTime=1 )
    @staticmethod
    def setMaxTime( val ):
        cmds.playbackOptions( maxTime=val ) 
       
    maxTime = property( getMaxTime, setMaxTime )
            
#env = Env()

_factories.createFunctions( __name__ )
