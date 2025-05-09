#
# Copyright OpenEmbedded Contributors
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Implements system state sampling. Called by buildstats.bbclass.
# Because it is a real Python module, it can hold persistent state,
# like open log files and the time of the last sampling.

import time
import re
import bb.event
from collections import deque

class SystemStats:
    def __init__(self, d):
        bn = d.getVar('BUILDNAME')
        bsdir = os.path.join(d.getVar('BUILDSTATS_BASE'), bn)
        bb.utils.mkdirhier(bsdir)
        file_handlers =  [('diskstats', self._reduce_diskstats),
                            ('meminfo', self._reduce_meminfo),
                            ('stat', self._reduce_stat),
                            ('net/dev', self._reduce_net)]

        # Some hosts like openSUSE have readable /proc/pressure files
        # but throw errors when these files are opened. Catch these error
        # and ensure that the reduce_proc_pressure directory is not created.
        if os.path.exists("/proc/pressure"):
            try:
                with open('/proc/pressure/cpu', 'rb') as source:
                    source.read()
                pressuredir = os.path.join(bsdir, 'reduced_proc_pressure')
                bb.utils.mkdirhier(pressuredir)
                file_handlers.extend([('pressure/cpu', self._reduce_pressure),
                                     ('pressure/io', self._reduce_pressure),
                                     ('pressure/memory', self._reduce_pressure)])
            except Exception:
                pass

        self.proc_files = []
        for filename, handler in (file_handlers):
            # The corresponding /proc files might not exist on the host.
            # For example, /proc/diskstats is not available in virtualized
            # environments like Linux-VServer. Silently skip collecting
            # the data.
            if os.path.exists(os.path.join('/proc', filename)):
                # In practice, this class gets instantiated only once in
                # the bitbake cooker process.  Therefore 'append' mode is
                # not strictly necessary, but using it makes the class
                # more robust should two processes ever write
                # concurrently.
                if filename == 'net/dev':
                    destfile = os.path.join(bsdir, 'reduced_proc_net.log')
                else:
                    destfile = os.path.join(bsdir, '%sproc_%s.log' % ('reduced_' if handler else '', filename))
                self.proc_files.append((filename, open(destfile, 'ab'), handler))
        self.monitor_disk = open(os.path.join(bsdir, 'monitor_disk.log'), 'ab')
        # Last time that we sampled /proc data resp. recorded disk monitoring data.
        self.last_proc = 0
        self.last_disk_monitor = 0
        # Minimum number of seconds between recording a sample. This becames relevant when we get
        # called very often while many short tasks get started. Sampling during quiet periods
        # depends on the heartbeat event, which fires less often.
        # By default, the Heartbeat events occur roughly once every second but the actual time
        # between these events deviates by a few milliseconds, in most cases. Hence
        # pick a somewhat arbitary tolerance such that we sample a large majority
        # of the Heartbeat events. This ignores rare events that fall outside the minimum
        # and may lead an extra sample in a given second every so often. However, it allows for fairly
        # consistent intervals between samples without missing many events.
        self.tolerance = 0.01
        self.min_seconds = 1.0 - self.tolerance

        self.meminfo_regex = re.compile(rb'^(MemTotal|MemFree|Buffers|Cached|SwapTotal|SwapFree):\s*(\d+)')
        self.diskstats_regex = re.compile(rb'^([hsv]d.|mtdblock\d|mmcblk\d|cciss/c\d+d\d+|nvme\d+n\d+.*)$')
        self.diskstats_ltime = None
        self.diskstats_data = None
        self.stat_ltimes = None
        # Last time we sampled /proc/pressure. All resources stored in a single dict with the key as filename
        self.last_pressure = {"pressure/cpu": None, "pressure/io": None, "pressure/memory": None}
        self.net_stats = {}

    def close(self):
        self.monitor_disk.close()
        for _, output, _ in self.proc_files:
            output.close()

    def _reduce_meminfo(self, time, data, filename):
        """
        Extracts 'MemTotal', 'MemFree', 'Buffers', 'Cached', 'SwapTotal', 'SwapFree'
        and writes their values into a single line, in that order.
        """
        values = {}
        for line in data.split(b'\n'):
            m = self.meminfo_regex.match(line)
            if m:
                values[m.group(1)] = m.group(2)
        if len(values) == 6:
            return (time,
                    b' '.join([values[x] for x in
                               (b'MemTotal', b'MemFree', b'Buffers', b'Cached', b'SwapTotal', b'SwapFree')]) + b'\n')

    def _reduce_net(self, time, data, filename):
        data = data.split(b'\n')
        for line in data[2:]:
            if b":" not in line:
                continue
            try:
                parts = line.split()
                iface = (parts[0].strip(b':')).decode('ascii')
                receive_bytes = int(parts[1])
                transmit_bytes = int(parts[9])
            except Exception:
                continue

            if iface not in self.net_stats:
                self.net_stats[iface] = deque(maxlen=2)
                self.net_stats[iface].append((receive_bytes, transmit_bytes, 0, 0))
            prev = self.net_stats[iface][-1] if self.net_stats[iface] else (0, 0, 0, 0)            
            receive_diff = receive_bytes - prev[0]
            transmit_diff = transmit_bytes - prev[1]
            self.net_stats[iface].append((
                receive_bytes,
                transmit_bytes,
                receive_diff,
                transmit_diff
            ))

        result_str = "\n".join(
            f"{iface}: {net_data[-1][0]} {net_data[-1][1]} {net_data[-1][2]} {net_data[-1][3]}"
            for iface, net_data in self.net_stats.items()
        ) + "\n"

        return time, result_str.encode('ascii')

    def _diskstats_is_relevant_line(self, linetokens):
        if len(linetokens) < 14:
            return False
        disk = linetokens[2]
        return self.diskstats_regex.match(disk)

    def _reduce_diskstats(self, time, data, filename):
        relevant_tokens = filter(self._diskstats_is_relevant_line, map(lambda x: x.split(), data.split(b'\n')))
        diskdata = [0] * 3
        reduced = None
        for tokens in relevant_tokens:
            # rsect
            diskdata[0] += int(tokens[5])
            # wsect
            diskdata[1] += int(tokens[9])
            # use
            diskdata[2] += int(tokens[12])
        if self.diskstats_ltime:
            # We need to compute information about the time interval
            # since the last sampling and record the result as sample
            # for that point in the past.
            interval = time - self.diskstats_ltime
            if interval > 0:
                sums = [ a - b for a, b in zip(diskdata, self.diskstats_data) ]
                readTput = sums[0] / 2.0 * 100.0 / interval
                writeTput = sums[1] / 2.0 * 100.0 / interval
                util = float( sums[2] ) / 10 / interval
                util = max(0.0, min(1.0, util))
                reduced = (self.diskstats_ltime, (readTput, writeTput, util))

        self.diskstats_ltime = time
        self.diskstats_data = diskdata
        return reduced


    def _reduce_nop(self, time, data, filename):
        return (time, data)

    def _reduce_stat(self, time, data, filename):
        if not data:
            return None
        # CPU times {user, nice, system, idle, io_wait, irq, softirq} from first line
        tokens = data.split(b'\n', 1)[0].split()
        times = [ int(token) for token in tokens[1:] ]
        reduced = None
        if self.stat_ltimes:
            user = float((times[0] + times[1]) - (self.stat_ltimes[0] + self.stat_ltimes[1]))
            system = float((times[2] + times[5] + times[6]) - (self.stat_ltimes[2] + self.stat_ltimes[5] + self.stat_ltimes[6]))
            idle = float(times[3] - self.stat_ltimes[3])
            iowait = float(times[4] - self.stat_ltimes[4])

            aSum = max(user + system + idle + iowait, 1)
            reduced = (time, (user/aSum, system/aSum, iowait/aSum))

        self.stat_ltimes = times
        return reduced

    def _reduce_pressure(self, time, data, filename):
        """
        Return reduced pressure: {avg10, avg60, avg300} and delta total compared to the previous sample
        for the cpu, io and memory resources. A common function is used for all 3 resources since the
        format of the /proc/pressure file is the same in each case.
        """
        if not data:
            return None
        tokens = data.split(b'\n', 1)[0].split()
        avg10 = float(tokens[1].split(b'=')[1])
        avg60 = float(tokens[2].split(b'=')[1])
        avg300 = float(tokens[3].split(b'=')[1])
        total = int(tokens[4].split(b'=')[1])

        reduced = None
        if self.last_pressure[filename]:
            delta = total - self.last_pressure[filename]
            reduced = (time, (avg10, avg60, avg300, delta))
        self.last_pressure[filename] = total
        return reduced

    def sample(self, event, force):
        """
        Collect and log proc or disk_monitor stats periodically.
        Return True if a new sample is collected and hence the value last_proc or last_disk_monitor
        is changed.
        """
        retval = False
        now = time.time()
        if (now - self.last_proc > self.min_seconds) or force:
            for filename, output, handler in self.proc_files:
                with open(os.path.join('/proc', filename), 'rb') as input:
                    data = input.read()
                    if handler:
                        reduced = handler(now, data, filename)
                    else:
                        reduced = (now, data)
                    if reduced:
                        if isinstance(reduced[1], bytes):
                            # Use as it is.
                            data = reduced[1]
                        else:
                            # Convert to a single line.
                            data = (' '.join([str(x) for x in reduced[1]]) + '\n').encode('ascii')
                        # Unbuffered raw write, less overhead and useful
                        # in case that we end up with concurrent writes.
                        os.write(output.fileno(),
                                 ('%.0f\n' % reduced[0]).encode('ascii') +
                                 data +
                                 b'\n')
            self.last_proc = now
            retval = True

        if isinstance(event, bb.event.MonitorDiskEvent) and \
           ((now - self.last_disk_monitor > self.min_seconds) or force):
            os.write(self.monitor_disk.fileno(),
                     ('%.0f\n' % now).encode('ascii') +
                     ''.join(['%s: %d\n' % (dev, sample.total_bytes - sample.free_bytes)
                              for dev, sample in event.disk_usage.items()]).encode('ascii') +
                     b'\n')
            self.last_disk_monitor = now
            retval = True
        return retval