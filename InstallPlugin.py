import sys
import platform
import os
import tempfile
import shutil
import subprocess
import glob
import json
import collections

scriptPath = os.path.realpath(os.getcwd())
pluginFile = os.path.join(scriptPath, "NoesisGUI.uplugin")
if not os.path.isfile(pluginFile):
	print "This script must be run from the NoesisGUI plugin directory. Exiting..."
	exit(1)

if not os.path.isfile(os.path.join(scriptPath, "Source", "Noesis", "NoesisSDK", "Include", "Noesis_pch.h")):
	print "You must install the NoesisGUI native SDK in Source/Noesis/NoesisSDK. Exiting..."
	exit(1)

if platform.platform().startswith("Windows"):
	hostPlatform = "Win64"
if platform.platform().startswith("Darwin"):
	hostPlatform = "Mac"

allInstallations = collections.OrderedDict()

try:
	import configparser
except:
	print "Module configparser not installed. Exiting..."
	exit(1)

if hostPlatform == "Win64":
	try:
		import win32api
		import win32con
	except:
		print "Module pywin32 not installed. Exiting..."
		exit(1)

	import ctypes
	from ctypes import wintypes, windll

	def getProgramDataPath():
		try:
			CSIDL_COMMON_APPDATA = 35

			_SHGetFolderPath = windll.shell32.SHGetFolderPathW
			_SHGetFolderPath.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.HANDLE, wintypes.DWORD, wintypes.LPCWSTR]

			path_buf = wintypes.create_unicode_buffer(wintypes.MAX_PATH)
			result = _SHGetFolderPath(0, CSIDL_COMMON_APPDATA, 0, 0, path_buf)
			return path_buf.value
		except:
			return ""

	programDataPath = getProgramDataPath()

	if programDataPath == "":
		print "Can't find application support folder" 
		exit(1)

	applicationSettingsPath = os.path.join(programDataPath, "Epic")

	installedListFile = os.path.join(applicationSettingsPath, "UnrealEngineLauncher", "LauncherInstalled.dat")
	if os.path.isfile(installedListFile):
		launcherInstalled = json.load(open(installedListFile))
		installationList = launcherInstalled["InstallationList"]
		if installationList is not None:
			for installation in installationList:
				appName = installation["AppName"]
				if appName.startswith("UE_"):
					appName = appName[3:]
					installLocation = installation["InstallLocation"]
					allInstallations[appName] = installLocation

	try:
		reghandle = win32api.RegOpenKeyEx(win32con.HKEY_CURRENT_USER,"SOFTWARE\\Epic Games\\Unreal Engine\\Builds", 0, win32con.KEY_ALL_ACCESS)
		index = 0
		while True:
			name, value, type = win32api.RegEnumValue(reghandle, index)
			allInstallations[name] = value
			index += 1
	except:
		pass

if hostPlatform == "Mac":
	try:
		import Cocoa
	except:
		print "Module pyobjc not installed. Exiting..."
		exit(1)

	applicationSupportPaths = Cocoa.NSSearchPathForDirectoriesInDomains(Cocoa.NSApplicationSupportDirectory, Cocoa.NSUserDomainMask, True)

	if len(applicationSupportPaths) == 0:
		print "Can't find application support folder" 
		exit(1)

	applicationSettingsPath = applicationSupportPaths[0].stringByAppendingPathComponent_("Epic")

	installedListFile = applicationSettingsPath.stringByAppendingPathComponent_("UnrealEngineLauncher").stringByAppendingPathComponent_("LauncherInstalled.dat")
	if os.path.isfile(installedListFile):
		launcherInstalled = json.load(open(installedListFile.cStringUsingEncoding_(Cocoa.NSUTF8StringEncoding)))
		installationList = launcherInstalled["InstallationList"]
		if installationList is not None:
			for installation in installationList:
				appName = installation["AppName"]
				if appName.startswith("UE_"):
					appName = appName[3:]
					installLocation = installation["InstallLocation"]
					allInstallations[appName] = installLocation

	configFile = applicationSettingsPath.stringByAppendingPathComponent_("UnrealEngine").stringByAppendingPathComponent_("Install.ini")
	if os.path.isfile(configFile):
		config = configparser.ConfigParser()
		config.read(configFile.cStringUsingEncoding_(Cocoa.NSUTF8StringEncoding))
		installations = config["Installations"]
		if installations is not None:
			allInstallations.update(installations)

print "Found the following engine installations:"
for id, path in allInstallations.items():
	print id + " = " +  path

engineInstall = False
installerEngineInstall = False
pluginEnginePath = None
for id, installation in allInstallations.items():
	enginePath = os.path.realpath(installation)
	if os.path.commonprefix([enginePath, scriptPath]) == enginePath:
		engineInstall = True
		if not id.startswith("{"):
			installerEngineInstall = True
		pluginEnginePath = enginePath
		print "Found engine for plugin at " + pluginEnginePath
		break

if pluginEnginePath is None:
	print "Plugin is not installed in any of the installed engines. Looking for projects..."
	currentPath, currentDir = os.path.split(scriptPath)
	while currentDir != "":
		projectFiles = glob.glob(os.path.join(currentPath, "*.uproject"))
		if projectFiles:
			projectFile = projectFiles[0]
			print "Found project for plugin at " + projectFile
			try:
				project = json.load(open(projectFile), object_pairs_hook=collections.OrderedDict)
				engineAssociation = project["EngineAssociation"]
				if engineAssociation is not None:
					if engineAssociation in allInstallations:
						pluginEnginePath = os.path.realpath(allInstallations[engineAssociation])
						print "Found associated engine at " + pluginEnginePath
						break
					else:
						print "Couldn't find an engine with id " + engineAssociation
						exit(1)
			except:
				print "Malformed project file. Exiting..."
				exit(1)
		currentPath, currentDir = os.path.split(currentPath)

if pluginEnginePath is None:
	print "Couldn't find an engine for the plugin. Exiting..."
	exit(1)

if not os.path.isdir(pluginEnginePath):
	print pluginEnginePath + " doesn't exist. Exiting..."
	exit(1)

if engineInstall:
	if installerEngineInstall:
		packagePath = tempfile.mkdtemp()
		packageCmdLine = ["-Package=" + packagePath]
		pluginCmdLine = ["-Plugin=" + pluginFile]
	else:
		projectFile = os.path.join(scriptPath, "NoesisGUI.uproject")
		projectCmdLine = ["-project=" + projectFile]
		project = { "FileVersion" : 3, "Plugins" : [ { "Name" : "NoesisGUI", "Enabled" : True } ] }
		json.dump(project, open(projectFile, "w+"))
else:
	projectCmdLine = ["-project=" + projectFile]
	if "Plugins" in project:
		foundPlugin = False
		plugins = project["Plugins"]
		for plugin in plugins:
			if plugin["Name"] == "NoesisGUI":
				foundPlugin = True
				if not plugin["Enabled"]:
					print "Project includes NoesisGUI plugin, but it's disabled. Enabling..."
					plugin["Enabled"] = True
		if not foundPlugin:
			print "Project does not include NoesisGUI plugin. Including..."
			plugins += [ collections.OrderedDict([("Name", "NoesisGUI"), ("Enabled", True)]) ]
	else:
		print "Project does not include NoesisGUI plugin. Including..."
		project["Plugins"] = [ collections.OrderedDict([("Name", "NoesisGUI"), ("Enabled", True)]) ]
	json.dump(project, open(projectFile, "w+"), indent=2, separators=(',', ': '))

if hostPlatform == "Win64":
	ubtFile = os.path.join(pluginEnginePath, "Engine", "Binaries", "DotNET", "UnrealBuildTool.exe")
	if not os.path.isfile(ubtFile):
		print pluginEnginePath + " doesn't appear to be a valid engine installation. Exiting..."
		exit(1)
	runUatFile = os.path.join(pluginEnginePath, "Engine", "Build", "BatchFiles", "RunUAT.bat")
	if not os.path.isfile(runUatFile):
			print pluginEnginePath + " doesn't appear to be a valid engine installation. Exiting..."
			exit(1)

	def build(target, configurations, platforms):
		modulesCmdLine = ["-module=NoesisRuntime"]
		if target == "UE4Editor":
			modulesCmdLine += ["-module=NoesisEditor"]
		else:
			modulesCmdLine += ["-ignorejunk"]
		for platform in platforms:
			for configuration in configurations:
				print "Building " + target + " " + configuration + " " + platform
				buildCmdLine = [ubtFile, target, platform, configuration, "-iwyu", "-nocreatestub", "-NoHotReload"] + modulesCmdLine + projectCmdLine
				process = subprocess.Popen(buildCmdLine)
				while process.poll() is None:
					stdout, stderr = process.communicate()
					if stdout is not None:
						print stdout

	def buildPlugin(platforms):
		hostPlatformCmdLine = []
		if hostPlatform not in platforms:
			hostPlatformCmdLine += ["-NoHostPlatform"]
		targetPlatformsCmdLine = ["-TargetPlatforms=" + '+'.join(platforms)]
		buildCmdLine = [runUatFile, "BuildPlugin"] + pluginCmdLine + targetPlatformsCmdLine + packageCmdLine + hostPlatformCmdLine
		process = subprocess.Popen(buildCmdLine)
		while process.poll() is None:
			stdout, stderr = process.communicate()
			if stdout is not None:
				print stdout

if hostPlatform == "Mac":
	monoFile = os.path.join(pluginEnginePath, "Engine", "Build", "BatchFiles", "Mac", "RunMono.sh")
	if not os.path.isfile(monoFile):
		print pluginEnginePath + " doesn't appear to be a valid engine installation. Exiting..."
		exit(1)
	ubtFile = os.path.join(pluginEnginePath, "Engine", "Binaries", "DotNET", "UnrealBuildTool.exe")
	if not os.path.isfile(ubtFile):
		print pluginEnginePath + " doesn't appear to be a valid engine installation. Exiting..."
		exit(1)
	runUatFile = os.path.join(pluginEnginePath, "Engine", "Build", "BatchFiles", "RunUAT.sh")
	if not os.path.isfile(runUatFile):
			print pluginEnginePath + " doesn't appear to be a valid engine installation. Exiting..."
			exit(1)

	def build(target, configurations, platforms):
		modulesCmdLine = ["-module=NoesisRuntime"]
		if target == "UE4Editor":
			modulesCmdLine += ["-module=NoesisEditor"]
		else:
			modulesCmdLine += ["-ignorejunk"]
		for platform in platforms:
			for configuration in configurations:
				print "Building " + target + " " + configuration + " " + platform
				buildCmdLine = [monoFile, ubtFile, target, platform, configuration, "-iwyu", "-nocreatestub", "-NoHotReload"] + modulesCmdLine + projectCmdLine
				process = subprocess.Popen(buildCmdLine)
				while process.poll() is None:
					stdout, stderr = process.communicate()
					if stdout is not None:
						print stdout

	def buildPlugin(platforms):
		hostPlatformCmdLine = []
		if hostPlatform not in platforms:
			hostPlatformCmdLine += ["-NoHostPlatform"]
		targetPlatformsCmdLine = ["-TargetPlatforms=" + '+'.join(platforms)]
		buildCmdLine = [runUatFile, "BuildPlugin"] + pluginCmdLine + targetPlatformsCmdLine + packageCmdLine + hostPlatformCmdLine
		process = subprocess.Popen(buildCmdLine)
		while process.poll() is None:
			stdout, stderr = process.communicate()
			if stdout is not None:
				print stdout

arguments = sys.argv[1:]

allowedPlatforms = [ "Win64", "Mac", "IOS", "Android", "PS4", "XboxOne" ]
excludedPlatforms = []

buildPlatforms = [hostPlatform]
for buildPlatform in arguments:
	if buildPlatform in allowedPlatforms:
		if buildPlatform not in excludedPlatforms:
			buildPlatforms += [buildPlatform]

if hostPlatform == "Win64":
	noesisDllPath = os.path.join(scriptPath, "Source", "Noesis", "NoesisSDK", "Bin", "windows_x86_64", "Noesis.dll")
	pluginEngineBinariesPath = os.path.join(pluginEnginePath, "Engine", "Binaries", "Win64")
	print "Copying " + noesisDllPath + " to " + pluginEngineBinariesPath
	shutil.copy2(noesisDllPath, pluginEngineBinariesPath)

if not installerEngineInstall:
	if not arguments:
		build("UE4Editor", ["Development"], [hostPlatform])
		build("UE4Game", ["Development", "Shipping"], [hostPlatform])
	else:
		if buildPlatforms:
			if hostPlatform in buildPlatforms:
				build("UE4Editor", ["Development"], [hostPlatform])
			build("UE4Game", ["Development", "Shipping"], buildPlatforms)
		else:
			print "No valid platforms specified. Exiting..."
else:
	print "Launcher engine installation detected. Using BuildPlugin"
	if not arguments:
		buildPlugin([hostPlatform])
	else:
		if buildPlatforms:
			buildPlugin(buildPlatforms)
		else:
			print "No valid platforms specified. Exiting..."

if engineInstall:
	if installerEngineInstall:
		dst = os.path.join(scriptPath, "Binaries")
		if not os.path.exists(dst):
			os.mkdir(dst)
		for root, dirs, files in os.walk(os.path.join(packagePath, "Binaries")):
			for item in files:
				src = os.path.join(root, item)
				dst = os.path.join(scriptPath, src.replace(packagePath, "")[1:])
				shutil.copy2(src, dst)
			for item in dirs:
				src = os.path.join(root, item)
				dst = os.path.join(scriptPath, src.replace(packagePath, "")[1:])
				if not os.path.exists(dst):
					os.mkdir(dst)
		dst = os.path.join(scriptPath, "Intermediate")
		if not os.path.exists(dst):
			os.mkdir(dst)
		for root, dirs, files in os.walk(os.path.join(packagePath, "Intermediate")):
			for item in files:
				src = os.path.join(root, item)
				dst = os.path.join(scriptPath, src.replace(packagePath, "")[1:])
				shutil.copy2(src, dst)
			for item in dirs:
				src = os.path.join(root, item)
				dst = os.path.join(scriptPath, src.replace(packagePath, "")[1:])
				if not os.path.exists(dst):
					os.mkdir(dst)
		shutil.rmtree(packagePath)
	else:
		os.remove(projectFile)