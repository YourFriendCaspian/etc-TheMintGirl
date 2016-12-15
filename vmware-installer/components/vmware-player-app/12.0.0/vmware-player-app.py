"""
Copyright 2008 VMware, Inc.  All rights reserved. -- VMware Confidential

VMware Player App component installer.
"""
from random import randint

GCONF_DEFAULTS = 'xml:readwrite:/etc/gconf/gconf.xml.defaults'
DEST = LIBDIR/'vmware'
CONFIG = DEST/'setup/vmware-config'
CUPSLIBDIR = LIBDIR/'cups'

# These get set in PostInstall
SETTINGS = \
    {'product.buildNumber': None,
     'player.product.version': None,
     'vix.config.version': None}

vmwareSentinel = '# Automatically generated by the VMware Installer - DO NOT REMOVE\n'

# Player and Workstation both depend on some configuration living
# in /etc/vmware
ETCDIR = Destination('/etc/vmware')

class PlayerApp(Installer):
   def PreTransactionInstall(self, old, new, upgrade):
      self.learnMoreText = self.GetFileText('doc/LearnMore.txt')

   def InitializeQuestions(self, old, new, upgrade):
      def _AddYesNo(key, text, html):
         value = self.GetAnswer(key)
         if value:
            qlevel = 'CUSTOM'
            default = value
         else:
            qlevel = 'REGULAR'
            default = 'yes'

         self.AddQuestion('YesNo',
                          key=key,
                          text=text,
                          required=False,
                          default=default,
                          html=html,
                          level=qlevel)

      _AddYesNo('softwareUpdateEnabled',
                'Would you like to check for product updates on startup?',
                ['Learn More', self.learnMoreText])
      _AddYesNo('dataCollectionEnabled',
                'Would you like to help make VMware software better by sending '
                'anonymous system data and usage statistics to VMware?',
                ['Learn More', self.learnMoreText])

   def InitializeInstall(self, old, new, upgrade):
      global CUPSLIBDIR
      # Initialize CUPSLIBDIR
      # XXX: LIBDIR should be properly calculated, to make this cleaner
      if (PREFIX/'lib64/cups').exists():
         CUPSLIBDIR = PREFIX/'lib64/cups'

      self.AddTarget('File', 'bin/*', BINDIR)
      self.AddTarget('File', 'sbin/*', SBINDIR)

      for d in [ 'desktop-directories', 'icons', 'mime']:
         self.AddTarget('File', 'share/%s/*' % d, DATADIR/d)

      if self.GetConfig('installShortcuts', component='vmware-installer') != 'no':
         self.AddTarget('File', 'share/applications/*', DATADIR/'applications')
         self.AddTarget('File', 'share/appdata/*', DATADIR/'appdata')

      self.AddTarget('File', 'lib/*', DEST)
      self.AddTarget('File', 'doc/*', DOCDIR/'vmware-player')
      self.AddTarget('File', 'etc/xdg/*', SYSCONFDIR/'xdg')
      self.AddTarget('File', 'etc/cups/*', SYSCONFDIR/'cups')
      self.AddTarget('File', 'etc/init.d/*', SYSCONFDIR/'init.d')
      self.AddTarget('File', 'var/*', '/var')

      # Link the Bus Logic driver floppy to the 'resources' directory for use
      # in easy install.
      for floppy in ['vmscsi.flp',
                     'pvscsi-Windows2003.flp',
                     'pvscsi-Windows2008.flp',
                     'pvscsi-WindowsXP.flp']:
         self.AddTarget('Link', DEST/('floppies/%s' % floppy),
                        DEST/('resources/%s' % floppy))

      # Symlink all binaries to appLoader.
      for i in [
            'thnuclnt',
            'vmplayer',
            'vmware-enter-serial',
            'licenseTool',
            'vmware-unity-helper',
            'vmware-fuseUI',
            'vmware-app-control',
            'vmware-zenity',
         ]:
         self.AddTarget('Link', DEST/'bin/appLoader', DEST/'bin'/i)

      self.SetPermission(DEST/'bin/*', BINARY)

      # .thnumod is an executable that just happens to live in /etc/thnuclnt,
      # and might as well be in /usr/bin or similar instead.  For SELinux systems,
      # files under /etc may be given an etc_t file context, which is off-limits
      # to the reduced privilege lp processes.
      #
      # To get around this (since we can't guarantee semanage is available to
      # properly and permanently relabel .thnumod), we'll just use a symlink to
      # appLoader and leave it at that.  (appLoader will have the lib_t context,
      # which is fine for CUPS filters.)
      self.AddTarget('Link', DEST/'bin/appLoader', SYSCONFDIR/'thnuclnt/.thnumod')

      self.AddTarget('File', 'extras/thnucups', CUPSLIBDIR/'filter/thnucups')
      self.SetPermission(CUPSLIBDIR/'filter/thnucups', BINARY)

      # Ubuntu 10.04 requires additional .desktop files in /usr/local/share/applications
      # If GNOME or Ubuntu is going this way, rather than just add these links for
      # Ubuntu 10.04, always add them for future-proofing.

      # Some linux distributions use yet another standard for DE metadata, requiring
      # .appdata.xml files in order for WS to be usable via the DE app launcher.
      # Like the .desktop files, just install them along with the rest for futureproofing.
      if self.GetConfig('installShortcuts', component='vmware-installer') != 'no':
         self.AddTarget('Link', DATADIR/'applications/vmware-player.desktop',
                        PREFIX/'local/share/applications/vmware-player.desktop')
         self.AddTarget('Link', DATADIR/'appdata/vmware-player.appdata.xml',
                        PREFIX/'local/share/appdata/vmware-player.appdata.xml')

      self.SetPermission(BINDIR/'vmware-mount', SETUID)

      themeIndex = DATADIR/'icons/hicolor/index.theme'

      # @todo: This should probably be treated as a SYSTEM file type
      # but it's not yet implemented.
      not themeIndex.exists() and self.AddTarget('File', 'files/index.theme', themeIndex)

   def _scriptRunnable(self, script):
      """ Returns True if the script exists and is in a runnable state """
      return script.isexe() and script.isfile() and self.RunCommand(script, 'validate').retCode == 100

   def _vmwareMountRunnable(self, vmwareMount):
      # vmware-mount may exist but if libfuse isn't installed we have
      # to check explicitly, otherwise it'll appear that disks are
      # mounted when in fact the program just can't be linked or
      # executed.
      #
      # We must check that -L works, otherwise there may be some
      # initialization error that will be improperly interpreted as
      # disks being mounted.
      return vmwareMount.exists() and self.RunCommand(vmwareMount, noLogging=True).retCode != 127 and \
          self.RunCommand(vmwareMount, '-L', noLogging=True).retCode == 0

   def InitializeUninstall(self, old, new, upgrade):
      vmwareMount = BINDIR/'vmware-mount'

      if self._vmwareMountRunnable(vmwareMount):
         # Unmount all virtual disks.
         if self.RunCommand(vmwareMount, '-X', noLogging=True).retCode == 0:
            log.Info('All virtual disks were unmounted successfully')
            return
         else:
            log.Error('Some virtual disks were unable to be unmounted')
            raise InstallError('Some virtual disks could not be unmounted.  Make '
                               'sure that all files opened on all virtual disks are '
                               'closed and then run this installer again.')
      else:
         log.Info('vmware-mount did not exist or was unable to be run')

   def _killVMwareProcesses(self, upgrade):
      self.RunCommand('killall',
                      'vmplayer', 'vmware', 'vmware-tray', 'vmware-unity-helper',
                      'vmware-enter-serial',
                      'vmnet-natd', 'vmnet-dhcpd',
                      'vmware-netcfg', 'vmnet-netifup', 'vmnet-bridge',
                      ignoreErrors=True, noLogging=True);
      # Don't kill fuseUI so we can keep the virtual disk mounted for upgrade.
      if not upgrade:
         self.RunCommand('killall', 'vmware-fuseUI',
                         ignoreErrors=True, noLogging=True);


   def PreInstall(self, old, new, upgrade):
      # Make sure we kill all processes that should not be running!
      self._killVMwareProcesses(upgrade)

   def PreUninstall(self, old, new, upgrade):
      self._deconfigureVMStreamingHandlers()

      # Deconfigure Services
      inits = self.LoadInclude('initscript')

      # This must be the last thing done since the actions above may
      # depend on it.
      for key in SETTINGS.keys():
         self.RunCommand(CONFIG, '-d', key)

      # Make sure we kill all processes that should not be running!
      self._killVMwareProcesses(upgrade)

   def PostUninstall(self, old, new, upgrade):
      VMNETS = 255

      keepConfig = self.GetConfig('keepConfigOnUninstall', component='vmware-installer')
      if not upgrade and keepConfig != 'yes':
         (ETCDIR/'networking').remove(ignore_errors=True)

      # Clean up bits and pieces that networking has left behind.
      for f in ETCDIR.walkfiles('networking.bak*'):
         f.remove(ignore_errors=True)

      for i in range(0, VMNETS + 1):
         vnet = ETCDIR/('vmnet%d' % i)
         vnet.exists() and vnet.rmtree(ignore_errors=True)

      # Remove link to deprecated uninstall mechanism
      self.RemoveUninstallLinks()

   def GetConfigValue(self, key):
      ret = self.RunCommand(CONFIG, '-g', key)
      if ret and ret.stdout:
         return ret.stdout.strip()
      return None

   def PostInstall(self, old, new, upgrade):
      # Used by VIX to locate correct provider.
      SETTINGS['player.product.version'] = new
      SETTINGS['vix.config.version'] = 1
      SETTINGS['product.buildNumber'] = self.GetManifestValue('buildNumber', '0')

      # only set the value in the config file when it has changed or wasn't there before:
      softwareUpdateEnabled = self.GetConfigValue('installerDefaults.autoSoftwareUpdateEnabled')
      if softwareUpdateEnabled == None or softwareUpdateEnabled != self.GetAnswer('softwareUpdateEnabled'):
         SETTINGS['installerDefaults.autoSoftwareUpdateEnabled'] = self.GetAnswer('softwareUpdateEnabled')
         SETTINGS['installerDefaults.autoSoftwareUpdateEnabled.epoch'] = '%s' % self.randomNumber()

      # only set the value in the config file when it has changed or wasn't there before:
      dataCollectionEnabled = self.GetConfigValue('installerDefaults.dataCollectionEnabled')
      if dataCollectionEnabled == None or dataCollectionEnabled != self.GetAnswer('dataCollectionEnabled'):
         SETTINGS['installerDefaults.dataCollectionEnabled'] = self.GetAnswer('dataCollectionEnabled')
         SETTINGS['installerDefaults.dataCollectionEnabled.epoch'] = '%s' % self.randomNumber()

      SETTINGS['installerDefaults.simplifiedUI'] = self.GetAnswer('simplifiedUI')

      SETTINGS['installerDefaults.supportURL'] = self.GetAnswer('supportURL')
      SETTINGS['componentDownload.server'] = self.GetAnswer('softwareUpdateURL')

      # Component Download should always be set to yes.
      # XXX: If this ever has a chance to change in the future, set the .epoch to generate
      # a random number like the above two settings.
      SETTINGS['installerDefaults.componentDownloadEnabled'] = 'yes'

      SETTINGS['installerDefaults.transferVersion'] = 1

      for key, val in SETTINGS.items():
         if val != "" and val != None:
            self.RunCommand(CONFIG, '-s', key, val)
         # when the setting is empty or unset remove it from the config file:
         else:
            self.RunCommand(CONFIG, '-d', key)

      launcher = DATADIR/'applications/vmware-player.desktop'
      binary = BINDIR/'vmplayer'
      self.RunCommand('sed', '-e', 's,@@BINARY@@,%s,g' % binary, '-i', launcher)

      self._configureVMStreamingHandlers()

      updateModule = self.LoadInclude('update')
      updateModule.UpdateIconCache(self, DATADIR)
      updateModule.UpdateMIME(self, DATADIR)

      # According to ThinPrint's setup.sh, SELinux systems may have issue with
      # thnucups context.  For now, ignore failures since they're harmless.
      restcon = path(self._which('restorecon'))
      if not restcon:
         restcon = path('/sbin/restorecon')
      if restcon.exists():
         self.RunCommand('restorecon', CUPSLIBDIR/'filter/thnucups', ignoreErrors=True)

      # restart cups
      script = INITSCRIPTDIR/'cups'
      if INITSCRIPTDIR and script.exists():
         self.RunCommand(script, 'restart', ignoreErrors=True)

      # Set up our service scripts.
      inits = self.LoadInclude('initscript')

      # We killed all running vmware processes before installing.  Restart all our
      # init scripts
      for scriptName in ['vmware']:
         script = INITSCRIPTDIR/scriptName
         if INITSCRIPTDIR and script.exists():
            self.RunCommand(script, 'stop', ignoreErrors=True)
            self.RunCommand(script, 'start', ignoreErrors=True)

      # Add link to deprecated uninstall mechanism to catch downgrades
      self.AddUninstallLinks()

   def _AddLineToFile(self, fil, text, addToEnd=True):
      """
      Add a line/consecutive lines to a file, surrounded by the VMware Sentinel.
      ### This method only adds a single line to a file ###
      ### You cannot make more than one modification per file ###

      @param fil: The file name.  Either a string or path object
      @param text: The text to add.  This function appends a \n
      @param addToEnd: Add to the end of the file?  If false, to the beginning.

      @return: True on successful modification, False if the file did not exist.
      """
      fil = path(fil) # Make sure it's a path object
      if fil.exists():
         txt = fil.bytes()
         # Modify the text
         if addToEnd:
            txt = ''.join([txt, vmwareSentinel, text, '\n', vmwareSentinel])
         else:
            txt = ''.join([vmwareSentinel, text, '\n', vmwareSentinel, txt])
         # Write it back to the file
         fil.write_bytes(txt)
         return True
      else:
         log.Info('Attempted to modify file %s, does not exist.' % fil)
         return False

   def _RemoveLineFromFile(self, fil):
      """
      Remove a line bracketed by the VMware Sentinel

      @param fil: The file name.  Either a string or path object

      @return: True on successful modification, False if the file did not exist.
      """
      fil = path(fil) # Make sure it's a path object
      if fil.exists():
         txt = fil.bytes()
         m = re.sub(vmwareSentinel + '.*\n' + vmwareSentinel,
                    '', txt, re.DOTALL)
         fil.write_bytes(m)
         return True
      else:
         log.Info('Attempted to modify file %s, does not exist.' % fil)
         return False

   def _configurePrelink(self, enable):
      """
      Configures prelinking by adding appLoader exclusion.

      @param enable: True if to add exclusion, False if to remove it.
      """
      prelink = path(u'/etc/prelink.conf')

      if prelink.exists():
         # XXX: It would probably be good to refactor this into some
         # sort of helper function that can add and remove lines from
         # files.
         skipPrelink = [ u'# appLoader will segfault if prelinked.',
                         u'-b %s' % (DEST/'bin/appLoader') ]

         lines = prelink.lines(encoding='utf-8', retain=False)

         # Strip whitespace from lines so that trailing whitespace
         # won't impact matching lines.
         lines = [line.strip() for line in lines]

         if enable:
            if skipPrelink[-1] not in lines:
               lines += skipPrelink
               log.Info(u'Added appLoader prelink exclusion to %s.', prelink)
            else:
               log.Warn(u'appLoader skip prelinking already present.')
         else:
            found = False

            for line in skipPrelink:
               if line in lines:
                  found = True
                  lines.remove(line)

            if found:
               log.Info(u'Removed appLoader prelink exclusion from %s.', prelink)

         # XXX: This can technically fail.  Actually, there are a
         # whole host of things that can fail in this function.  On
         # one hand we would like to catch errors and correct them
         # while being fairly resilient at installation time.
         #
         # One option might be to have a @failok decoration for things
         # that can fail loudly for internal builds but do not cause
         # installations to fail in release builds.
         prelink.write_lines(lines, encoding='utf-8')
      else:
         log.Info('Prelink not present, skipping configuration.')

   def _isGConfUsable(self):
      """ Return True if GConf settings can be configured, otherwise False """
      return self.RunCommand('gconftool-2', '--help', ignoreErrors=True, noLogging=True).retCode == 0

   def _configureVMStreamingHandlers(self):
      """ Configures handlers for vm:// and vms:// used for VM streaming """
      def configureGConf():
         # If Player isn't being installed as a product then
         # Workstation must be.
         if self.isProduct:
            target = BINDIR/'vmplayer'
         else:
            target = BINDIR/'vmware'

         target = self._escape(target)

         settings = (
            ('string', '/desktop/gnome/url-handlers/%s/command', '%s "%%s"' % target),
            ('bool', '/desktop/gnome/url-handlers/%s/enabled', 'true'),
            ('bool', '/desktop/gnome/url-handlers/%s/needs_terminal', 'false'),
         )

         for handler in ('vm', 'vms'):
            for gconfType, key, value in settings:
               key = key % handler
               self.RunCommand('gconftool-2', '--direct', '--config-source', GCONF_DEFAULTS,
                               '--type', gconfType, '--set', key, value)

         # Instruct all gconfd daemons to reload.
         self.RunCommand('killall', '-HUP', 'gconfd-2')

      self._isGConfUsable() and configureGConf()

   def _deconfigureVMStreamingHandlers(self):
      """ Deconfigures the handlers for vm:// and vms:// used for VM streaming"""
      def deconfigureGConf():
         for handler in ('vm', 'vms'):
            self.RunCommand('gconftool-2', '--direct', '--config-source', GCONF_DEFAULTS,
                            '--recursive-unset', '/desktop/gnome/url-handlers/%s' % handler)

         # Instruct all gconfd daemons to reload.
         self.RunCommand('killall', '-HUP', 'gconfd-2')

      self._isGConfUsable() and deconfigureGConf()

   def _escape(self, string):
      """ Escapes a string for use in a shell context """
      # XXX: Borrowed from util/shell.py: Escape.  Break that into a component-side
      # include file and remove this method once that's done.
      return "'%s'" % string.replace("'", '"\'"')

   # XXX: Remove this code duplication
   # XXX: Duplicated with vmware-vix.py, but until the
   # infrastructure exists to include these two functions properly,
   # it must be duplicated.
   def AddUninstallLinks(self, suffix=None):
      extension = ''
      if suffix:
         extension = '-%s' % suffix

      uninstaller = 'vmware-uninstall%s' % extension

      links = [BINDIR/uninstaller,
               SYSCONFDIR/('vmware%s/installer.sh' % extension)]

      # Remove the old file/links
      for link in links:
         try:
            link.remove()
         except OSError:
            # We don't care if it already doesn't exist.
            pass

         # Create installer hooks.  symlink expects a string and can't convert
         # a ComponentDestination object.  Convert them manually.
         try:
            BINDIR.makedirs()
         except OSError:
            # It's okay if it already exists.
            pass

         bin = LIBDIR/'vmware-installer/@@VMIS_VERSION@@'
         bin.perm = BINARY
         path(bin/'vmware-uninstall-downgrade').symlink(str(link))

      locationsFile = SYSCONFDIR/('vmware%s/locations' % extension)
      locationsFile.write_bytes('# Empty locations file to catch downgrade\n'
                                '# to WS 6.0\n')

   def RemoveUninstallLinks(self, suffix=None):
      extension = ''
      if suffix:
         extension = '-%s' % suffix

      uninstaller = 'vmware-uninstall%s' % extension

      links = [BINDIR/uninstaller,
               SYSCONFDIR/('vmware%s/installer.sh' % extension)]

      for link in links:
         try:
            link.remove()
         except OSError:
            # We don't care if it already doesn't exist.
            pass

      locationsFile = SYSCONFDIR/('vmware%s/locations' % extension)
      if locationsFile.exists():
         locationsFile.remove()

   def SystemType(self):
      """
      Returns a tuple of results for the system found.
      (sysName = 'Ubuntu', 'RHEL', 'SLE', 'Fedora', or None
       sysVersion = The system version or None
       sysExtra) = Desktop or Server (RHEL, SLE) or None
      """
      # We must scan through these in order.  SuSE systems for example
      # have a /etc/lsb-release file AND a /etc/SuSE-release file.  The
      # latter contains the right information.
      possibles = ('/etc/lsb-release', '/etc/redhat-release',
                   '/etc/SuSE-release', '/etc/fedora-release')

      txt = ''
      for p in possibles:
         fil = path(p)
         if fil.exists():
            txt = fil.bytes()

      if txt == '':
         log.Warn('No release file found...')
         return (None, None, None)

      sysName = ''
      sysVersion = ''
      sysExtra = ''

      # All sorts of things can go wrong with this...  Let's not die if it does.
      try:
         if re.findall('DISTRIB_ID=Ubuntu', txt):
            sysName = 'Ubuntu'
            mt = re.findall('DISTRIB_RELEASE=\d+\.\d+', txt)
            sysVersion = re.sub('DISTRIB_RELEASE=', '', mt[0])

         elif re.findall('Red Hat Enterprise Linux', txt):
            sysName = 'RHEL'
            mt = re.findall('elease \d+\.\d+', txt)
            sysVersion = re.sub('elease ', '', mt[0])
            mt = re.findall('Enterprise Linux \w+', txt)
            sysExtra = re.sub('Enterprise Linux ', '', mt[0])

         elif re.findall('SUSE Linux Enterprise', txt):
            sysName = 'SLE'
            mt = re.findall('VERSION = \d+', txt)
            sysVersion = re.sub('VERSION = ', '', mt[0])
            mt = re.findall('Enterprise \w+ ', txt)
            sysExtra = re.sub('Enterprise ', '', mt[0])

         elif re.findall('Fedora release', txt):
            sysName = 'Fedora'
            mt = re.findall('Fedora release \d+', txt)
            sysVersion = re.sub('Fedora release ', '', mt[0])

      except Exception:
         log.Warn('Could not determine system type...  Exception caught.')
         log.Warn('Found text reads:')
         log.Warn(txt)
         pass

      return (sysName, sysVersion, sysExtra)

   def _which(self, program):
      """
      Gets the PATH environment variable and checks for program
      in order.

      @param program: Executable to search for
      @returns: Full path if found and executable, None otherwise
      """
      systemPath = ENV['PATH']
      paths = systemPath.split(':')
      for p in paths:
         fullPath = path(p)/program
         if fullPath.isexe():
            return str(fullPath) # Return a string, not a path object

      return None

   def randomNumber(self):
      return randint(1000000000, 9999999999)
