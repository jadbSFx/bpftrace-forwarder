import json
import sys
import numbers
from argparse import ArgumentParser

from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter

desc = ('parse-trace-data reads a stream of output from bpftrace and parses out the datapoints from the stream.')

parser = ArgumentParser(description=desc)
parser.add_argument('-d', '--dimension', default='process', help='set dimension key value (default="process")')
parser.add_argument('-v', '--verbose', default=False, action='store_true', help='verbose mode, also echo input to stdout')
parser.add_argument('-t', '--test', default=False, action='store_true', help='test mode, send output to console')
parser.add_argument('metric',  help='metric name to report')
clargs = parser.parse_args()

key="process"

if clargs.dimension is not None:
    key = clargs.dimension

#set up otlp exporter, etc.

if clargs.test:
	exporter = ConsoleMetricExporter()
else:
	#export to default localhost:4317
	exporter = OTLPMetricExporter(insecure=True)

reader = PeriodicExportingMetricReader(exporter)
provider = MeterProvider(metric_readers=[reader])

meter = provider.get_meter("bpftrace-forwarder","0.0.1")
counter = meter.create_counter(clargs.metric)

#read initial output line ("attached_probes")
lineinput = str(sys.stdin.readline())
if clargs.verbose:
	print(lineinput, end="")

try:
	jdata = json.loads(lineinput)
except:
	sys.exit('Error parsing first line, expecting JSON data, did you run bpftrace with "-f json" ?')

while True:
	lineinput = str(sys.stdin.readline())
	if clargs.verbose:
		print(lineinput, end="")
	try:
		jdata = json.loads(lineinput)
		data = jdata['data']
		if len(data) != 1:
			sys.exit('expecting data length = 1, unexpected input')
		else:
			dvalue = data["@"]
			if isinstance(dvalue, numbers.Number):
				#print('Metric Value - (%s, %d)' % (clargs.metric,dvalue))
				counter.add(dvalue)
			else:
				if isinstance(dvalue, dict):
					for key, value in dvalue.items():
						#print('Metric Value - (%s{%s}, %d)' % (clargs.metric, key, value))
						dims = {}
						dims[clargs.dimension] = key
						counter.add(value, dims)
				else:
					sys.exit('expecting Number type, unexpected input')
		# flush data to local collector
		provider.force_flush()
	except:
		if len(data) < 2:
			# single character line is normal terminating condition
			break
		sys.exit('Error parsing input, expecting JSON data, did you run bpftrace with "-f json" ?')
		pass