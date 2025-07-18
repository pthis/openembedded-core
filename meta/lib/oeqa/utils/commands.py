#
# Copyright (c) 2013-2014 Intel Corporation
#
# SPDX-License-Identifier: MIT
#

# DESCRIPTION
# This module is mainly used by scripts/oe-selftest and modules under meta/oeqa/selftest
# It provides a class and methods for running commands on the host in a convienent way for tests.

import os
import sys
import subprocess
import threading
import time
import logging
from oeqa.utils import CommandError
from oeqa.utils import ftools
import re
import contextlib
import errno
# Export test doesn't require bb
try:
    import bb
except ImportError:
    pass

class Command(object):
    def __init__(self, command, bg=False, timeout=None, data=None, output_log=None, **options):

        self.defaultopts = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "stdin": None,
            "shell": False,
            "bufsize": -1,
        }

        self.cmd = command
        self.bg = bg
        self.timeout = timeout
        self.data = data

        self.options = dict(self.defaultopts)
        if isinstance(self.cmd, str):
            self.options["shell"] = True
        if self.data:
            self.options['stdin'] = subprocess.PIPE
        self.options.update(options)

        self.status = None
        # We collect chunks of output before joining them at the end.
        self._output_chunks = []
        self._error_chunks = []
        self.output = None
        self.error = None
        self.threads = []

        self.output_log = output_log
        self.log = logging.getLogger("utils.commands")

    def run(self):
        self.process = subprocess.Popen(self.cmd, **self.options)

        def readThread(output, stream, logfunc):
            if logfunc:
                for line in stream:
                    output.append(line)
                    logfunc(line.decode("utf-8", errors='replace').rstrip())
            else:
                output.append(stream.read())

        def readStderrThread():
            readThread(self._error_chunks, self.process.stderr, self.output_log.error if self.output_log else None)

        def readStdoutThread():
            readThread(self._output_chunks, self.process.stdout, self.output_log.info if self.output_log else None)

        def writeThread():
            try:
                self.process.stdin.write(self.data)
                self.process.stdin.close()
            except OSError as ex:
                # It's not an error when the command does not consume all
                # of our data. subprocess.communicate() also ignores that.
                if ex.errno != errno.EPIPE:
                    raise

        # We write in a separate thread because then we can read
        # without worrying about deadlocks. The additional thread is
        # expected to terminate by itself and we mark it as a daemon,
        # so even it should happen to not terminate for whatever
        # reason, the main process will still exit, which will then
        # kill the write thread.
        if self.data:
            thread = threading.Thread(target=writeThread, daemon=True)
            thread.start()
            self.threads.append(thread)
        if self.process.stderr:
            thread = threading.Thread(target=readStderrThread)
            thread.start()
            self.threads.append(thread)
        if self.output_log:
            self.output_log.info('Running: %s' % self.cmd)
        thread = threading.Thread(target=readStdoutThread)
        thread.start()
        self.threads.append(thread)

        self.log.debug("Running command '%s'" % self.cmd)

        if not self.bg:
            if self.timeout is None:
                for thread in self.threads:
                    thread.join()
            else:
                deadline = time.time() + self.timeout
                for thread in self.threads:
                    timeout = deadline - time.time()
                    if timeout < 0:
                        timeout = 0
                    thread.join(timeout)
            self.stop()

    def stop(self):
        for thread in self.threads:
            if thread.is_alive():
                self.process.terminate()
            # let's give it more time to terminate gracefully before killing it
            thread.join(5)
            if thread.is_alive():
                self.process.kill()
                thread.join()

        def finalize_output(data):
            if not data:
                data = ""
            else:
                data = b"".join(data)
                data = data.decode("utf-8", errors='replace').rstrip()
            return data

        self.output = finalize_output(self._output_chunks)
        self._output_chunks = None
        # self.error used to be a byte string earlier, probably unintentionally.
        # Now it is a normal string, just like self.output.
        self.error = finalize_output(self._error_chunks)
        self._error_chunks = None
        # At this point we know that the process has closed stdout/stderr, so
        # it is safe and necessary to wait for the actual process completion.
        self.status = self.process.wait()
        self.process.stdout.close()
        if self.process.stderr:
            self.process.stderr.close()

        self.log.debug("Command '%s' returned %d as exit code." % (self.cmd, self.status))
        # logging the complete output is insane
        # bitbake -e output is really big
        # and makes the log file useless
        if self.status:
            lout = "\n".join(self.output.splitlines()[-20:])
            self.log.debug("Last 20 lines:\n%s" % lout)


class Result(object):
    pass


def runCmd(command, ignore_status=False, timeout=None, assert_error=True, sync=True,
          native_sysroot=None, target_sys=None, limit_exc_output=0, output_log=None, **options):
    result = Result()

    if native_sysroot:
        new_env = dict(options.get('env', os.environ))
        paths = new_env["PATH"].split(":")
        paths = [
            os.path.join(native_sysroot, "bin"),
            os.path.join(native_sysroot, "sbin"),
            os.path.join(native_sysroot, "usr", "bin"),
            os.path.join(native_sysroot, "usr", "sbin"),
        ] + paths
        if target_sys:
            paths = [os.path.join(native_sysroot, "usr", "bin", target_sys)] + paths
        new_env["PATH"] = ":".join(paths)
        options['env'] = new_env

    cmd = Command(command, timeout=timeout, output_log=output_log, **options)
    cmd.run()

    # tests can be heavy on IO and if bitbake can't write out its caches, we see timeouts.
    # call sync around the tests to ensure the IO queue doesn't get too large, taking any IO
    # hit here rather than in bitbake shutdown.
    if sync:
        p = os.environ['PATH']
        os.environ['PATH'] = "/usr/bin:/bin:/usr/sbin:/sbin:" + p
        os.system("sync")
        os.environ['PATH'] = p

    result.command = command
    result.status = cmd.status
    result.output = cmd.output
    result.error = cmd.error
    result.pid = cmd.process.pid

    if result.status and not ignore_status:
        exc_output = result.output
        if result.error:
            exc_output = exc_output + result.error
        if limit_exc_output > 0:
            split = result.output.splitlines()
            if len(split) > limit_exc_output:
                exc_output = "\n... (last %d lines of output)\n" % limit_exc_output + \
                             '\n'.join(split[-limit_exc_output:])
        if assert_error:
            raise AssertionError("Command '%s' returned non-zero exit status %d:\n%s" % (command, result.status, exc_output))
        else:
            raise CommandError(result.status, command, exc_output)

    return result


def bitbake(command, ignore_status=False, timeout=None, postconfig=None, output_log=None, **options):

    if postconfig:
        postconfig_file = os.path.join(os.environ.get('BUILDDIR'), 'oeqa-post.conf')
        ftools.write_file(postconfig_file, postconfig)
        extra_args = "-R %s" % postconfig_file
    else:
        extra_args = ""

    if isinstance(command, str):
        cmd = "bitbake " + extra_args + " " + command
    else:
        cmd = [ "bitbake" ] + [a for a in (command + extra_args.split(" ")) if a not in [""]]

    try:
        return runCmd(cmd, ignore_status, timeout, output_log=output_log, **options)
    finally:
        if postconfig:
            os.remove(postconfig_file)


def get_bb_env(target=None, postconfig=None):
    if target:
        return bitbake("-e %s" % target, postconfig=postconfig).output
    else:
        return bitbake("-e", postconfig=postconfig).output

def get_bb_vars(variables=None, target=None, postconfig=None):
    """Get values of multiple bitbake variables"""
    bbenv = get_bb_env(target, postconfig=postconfig)

    if variables is not None:
        variables = list(variables)
    var_re = re.compile(r'^(export )?(?P<var>\w+(_.*)?)="(?P<value>.*)"$')
    unset_re = re.compile(r'^unset (?P<var>\w+)$')
    lastline = None
    values = {}
    for line in bbenv.splitlines():
        match = var_re.match(line)
        val = None
        if match:
            val = match.group('value')
        else:
            match = unset_re.match(line)
            if match:
                # Handle [unexport] variables
                if lastline.startswith('#   "'):
                    val = lastline.split('"')[1]
        if val:
            var = match.group('var')
            if variables is None:
                values[var] = val
            else:
                if var in variables:
                    values[var] = val
                    variables.remove(var)
                # Stop after all required variables have been found
                if not variables:
                    break
        lastline = line
    if variables:
        # Fill in missing values
        for var in variables:
            values[var] = None
    return values

def get_bb_var(var, target=None, postconfig=None):
    if postconfig:
        return bitbake("-e %s" % target or "", postconfig=postconfig).output
    else:
        # Fast-path for the non-postconfig case
        cmd = ["bitbake-getvar", "--quiet", "--value", var]
        if target:
            cmd.extend(["--recipe", target])
        try:
            return subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
        except subprocess.CalledProcessError as e:
            # We need to return None not the empty string if the variable hasn't been set.
            if e.returncode == 1:
                return None
            raise

def get_test_layer(bblayers=None):
    if bblayers is None:
        bblayers = get_bb_var("BBLAYERS")
    layers = bblayers.split()
    testlayer = None
    for l in layers:
        if '~' in l:
            l = os.path.expanduser(l)
        if "/meta-selftest" in l and os.path.isdir(l):
            testlayer = l
            break
    return testlayer

def create_temp_layer(templayerdir, templayername, priority=999, recipepathspec='recipes-*/*'):
    os.makedirs(os.path.join(templayerdir, 'conf'))
    corenames = get_bb_var('LAYERSERIES_CORENAMES')
    with open(os.path.join(templayerdir, 'conf', 'layer.conf'), 'w') as f:
        f.write('BBPATH .= ":${LAYERDIR}"\n')
        f.write('BBFILES += "${LAYERDIR}/%s/*.bb \\' % recipepathspec)
        f.write('            ${LAYERDIR}/%s/*.bbappend"\n' % recipepathspec)
        f.write('BBFILE_COLLECTIONS += "%s"\n' % templayername)
        f.write('BBFILE_PATTERN_%s = "^${LAYERDIR}/"\n' % templayername)
        f.write('BBFILE_PRIORITY_%s = "%d"\n' % (templayername, priority))
        f.write('BBFILE_PATTERN_IGNORE_EMPTY_%s = "1"\n' % templayername)
        f.write('LAYERSERIES_COMPAT_%s = "%s"\n' % (templayername, corenames))

@contextlib.contextmanager
def runqemu(pn, ssh=True, runqemuparams='', image_fstype=None, launch_cmd=None, qemuparams=None, overrides={}, boot_patterns = {}, discard_writes=True):
    """
    Starts a context manager for a 'oeqa.targetcontrol.QemuTarget' resource.
    The underlying Qemu will be booted into a shell when the generator yields
    and stopped when the 'with' block exits.

    Usage:

        with runqemu('core-image-minimal') as qemu:
            qemu.run_serial('cat /proc/cpuinfo')

    Args:
        pn (str): (image) recipe to run on
        ssh (boolean): whether or not to enable SSH (network access)
        runqemuparams (str): space-separated list of params to pass to 'runqemu' script (like 'nographics', 'ovmf', etc.)
        image_fstype (str): IMAGE_FSTYPE to use
        launch_cmd (str): directly run this command and bypass automatic runqemu parameter generation
        overrides (dict): dict of "'<bitbake-variable>': value" pairs that allows overriding bitbake variables
        boot_patterns (dict): dict of "'<pattern-name>': value" pairs to override default boot patterns, e.g. when not booting Linux
        discard_writes (boolean): enables qemu -snapshot feature to prevent modifying original image
    """

    import bb.tinfoil
    import bb.build

    # Need a non-'BitBake' logger to capture the runner output
    targetlogger = logging.getLogger('TargetRunner')
    targetlogger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    targetlogger.addHandler(handler)

    tinfoil = bb.tinfoil.Tinfoil()
    tinfoil.prepare(config_only=False, quiet=True)
    try:
        tinfoil.logger.setLevel(logging.WARNING)
        import oeqa.targetcontrol
        recipedata = tinfoil.parse_recipe(pn)
        recipedata.setVar("TEST_LOG_DIR", "${WORKDIR}/testimage")
        recipedata.setVar("TEST_QEMUBOOT_TIMEOUT", "1000")
        # Tell QemuTarget() whether need find rootfs/kernel or not
        if launch_cmd:
            recipedata.setVar("FIND_ROOTFS", '0')
        else:
            recipedata.setVar("FIND_ROOTFS", '1')

        for key, value in overrides.items():
            recipedata.setVar(key, value)

        logdir = recipedata.getVar("TEST_LOG_DIR")

        qemu = oeqa.targetcontrol.QemuTarget(recipedata, targetlogger, image_fstype, boot_patterns=boot_patterns)
    finally:
        # We need to shut down tinfoil early here in case we actually want
        # to run tinfoil-using utilities with the running QEMU instance.
        # Luckily QemuTarget doesn't need it after the constructor.
        tinfoil.shutdown()

    try:
        qemu.deploy()
        try:
            qemu.start(params=qemuparams, ssh=ssh, runqemuparams=runqemuparams, launch_cmd=launch_cmd, discard_writes=discard_writes)
        except Exception as e:
            msg = str(e) + '\nFailed to start QEMU - see the logs in %s' % logdir
            if os.path.exists(qemu.qemurunnerlog):
                with open(qemu.qemurunnerlog, 'r') as f:
                    msg = msg + "Qemurunner log output from %s:\n%s" % (qemu.qemurunnerlog, f.read())
            raise Exception(msg)

        yield qemu

    finally:
        targetlogger.removeHandler(handler)
        qemu.stop()

def runqemu_check_taps():
    """Check if tap devices for runqemu are available"""
    if not os.path.exists('/etc/runqemu-nosudo'):
        return False
    result = runCmd('PATH="$PATH:/sbin:/usr/sbin" ip tuntap show mode tap', ignore_status=True)
    if result.status != 0:
        return False
    for line in result.output.splitlines():
        if 'tap' in line:
            break
    else:
        return False
    return True

def updateEnv(env_file):
    """
    Source a file and update environment.
    """

    cmd = ". %s; env -0" % env_file
    result = runCmd(cmd)

    for line in result.output.split("\0"):
        (key, _, value) = line.partition("=")
        os.environ[key] = value
