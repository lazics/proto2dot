#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Generate graphviz dot files from Google Protocol Buffer definitions
"""

import os
import sys
import logging
import tempfile
import subprocess
import shutil
import glob
import importlib
import traceback
import StringIO
import copy
import pprint
import re

from google.protobuf import descriptor
from google.protobuf import reflection

__version__	= "1.0"
__author__	= "Laszlo Bako-Szabo"
__email__	= "lazics@gmail.com"
__license__	= "GPLv3"

class Proto2Dot(object):
	output = None
	files = None
	messages = None

	def __init__(self, options):
		self.options = options

		self.messages = {}
		self.output = {
			'nodes': {},
			'connections': [],
		}
		
		self.files = {}

		self.field_types_by_value={}

		for field_descr_n, field_descr_v in descriptor.FieldDescriptor.__dict__.iteritems():
			if not field_descr_n.startswith('TYPE_'):
				continue
			self.field_types_by_value[ field_descr_v ] = field_descr_n[ 5 : ].lower()

	def field_multiplicity(self, field):
		if field.label == field.LABEL_REQUIRED:
			return ("[1..1]", "required" )
		if field.label == field.LABEL_OPTIONAL:
			return ("[0..1]", "optional" )
		if field.label == field.LABEL_REPEATED:
			return ("[0..n]", "repeated" )
		raise Exception("Unknown field label");

	def check_port_side(self, field):
		#~ logging.debug("field.name: %s", field.name)
		base_prev = re.match('^([^0-9]*([0-9]+[^0-9]+)*)[0-9]*$', self.prev_field_name).group(1)
		m = re.match('^([^0-9]*([0-9]+[^0-9]+)*)[0-9]*$', field.name)
		base_cur = m.group(1)
		if base_prev != base_cur:
			self.port_on_left_side = not self.port_on_left_side
		self.prev_field_name = field.name

	def is_excluded(self, name):
		if self.options.exclude:
			for p in self.options.exclude:
				if ( re.match( ".*"+p+".*", name, re.IGNORECASE ) is not None ):
					return True
		return False

	def process_message_class(self, message):
		if self.is_excluded(message.name):
			logging.debug("message '%s' excluded" % (message.name, ) )
			return

		logging.debug("processing message %s" % (message.name,))

		self.messages[ message.name ] = message

		self.output["nodes"][ message.name ]="""
	%(name)s [
		shape = plaintext
		label = """ % {
	"name": message.name,
}

		self.output["nodes"][ message.name ]+="<<TABLE BORDER=\"0\" CELLBORDER=\"1\" CELLSPACING=\"0\" ALIGN=\"LEFT\" VALIGN=\"TOP\"><TR><TD COLSPAN=\"4\"><B>"+ message.name +"</B></TD></TR>"

		self.prev_field_name = ''
		self.port_on_left_side = True
		for field in message.fields:

			if self.is_excluded(field.name):
				logging.debug("field '%s->%s' excluded" % (message.name, field.name, ) )
				continue

			self.output["nodes"][ message.name ] += "<TR>"

			port = " PORT=\"l_" + field.name + "\""
			self.check_port_side( field )

			# field number
			self.output["nodes"][ message.name ] += ("<TD %s>" % ( port if self.port_on_left_side else "", ) )+ str(field.number) +"</TD>" 

			# field multiplicity
			mult, label = self.field_multiplicity( field )
			
			self.output["nodes"][ message.name ] += "<TD TITLE=\""+ label +"\">" + mult + "</TD>"

			# field type
			self.output["nodes"][ message.name ] +=	"<TD ALIGN=\"LEFT\"><FONT COLOR=\"#444444\">&lt;" + self.field_types_by_value[ field.type ] + "&gt;</FONT></TD>"

			# field name with connection port
			self.output["nodes"][ message.name ] +=	"<TD ALIGN=\"LEFT\" %s>" % ( ( port if not self.port_on_left_side else "" ), )


			if field.type == field.TYPE_ENUM:
				# enum field, display a list of values
				self.output["nodes"][ message.name ] += "<TABLE BORDER=\"0\" CELLBORDER=\"0\" CELLSPACING=\"0\"  ALIGN=\"LEFT\" VALIGN=\"TOP\"><TR><TD COLSPAN=\"3\" ALIGN=\"LEFT\">"+ field.name +"</TD></TR>"
				for e in field.enum_type.values:
					self.output["nodes"][ message.name ] += "<TR><TD WIDTH=\"10\"></TD><TD ALIGN=\"LEFT\"><FONT POINT-SIZE=\""+ str(self.options.font_size - 2) +"\">["+ str(e.number) +"]</FONT></TD><TD ALIGN=\"LEFT\"><I><FONT POINT-SIZE=\""+ str(self.options.font_size - 2) +"\">"+ e.name +"</FONT></I></TD></TR>"
				self.output["nodes"][ message.name ] += "</TABLE>"
			else:
				# not an enum, just display the name
				self.output["nodes"][ message.name ] += field.name
			self.output["nodes"][ message.name ] += "</TD>"


			# reference to another message
			if field.type == field.TYPE_MESSAGE:
				self.output["connections"].append( "\t\t"+ message.name +":l_"+ field.name + " -> " + field.message_type.name )

			self.output["nodes"][ message.name ] += "</TR>"


		self.output["nodes"][ message.name ]+="</TABLE>>"

		self.output["nodes"][ message.name ]+="""
	]
""" % {
	"name": message.name,
}

	def generate_dot_graph(self):
		f = StringIO.StringIO()
		f.write( """
digraph protobuf {
	fontname = "%(font_type)s"
	fontsize = %(font_size)s
	node [
		shape = record
		fontname = "%(font_type)s"
		fontsize = %(font_size)s
	]
	edge [
		fontname = "%(font_type)s"
		fontsize = %(font_size)s
		arrowhead = "empty"
	]
""" % {
	"font_type": self.options.font_type,
	"font_size": self.options.font_size,
})

		f.write( '\n'.join(self.output["nodes"].values()) )
		f.write( '\n'.join(self.output["connections"]) )

		f.write( """
}
""")
		graph = f.getvalue()
		f.close()

		return graph

def main():
	from optparse import OptionParser

	parser = OptionParser()
	parser.usage = "%prog [options] <proto files>"

	parser.add_option( "-o", "--output", dest="output", help="Output directory", type="string", default="." )
	parser.add_option( "-c", "--protoc", dest="protoc", help="Protocol buffer compiler", type="string", default="protoc" )
	parser.add_option( "-I", "--proto_path", dest="proto_path", help="directory in which to search for imports (passed as command-line argument to protoc)", action="append", type="string" )
	parser.add_option( "-x", "--exclude", dest="exclude", help="Exclude field/message names matching the specified regexp pattern", type="string", action="append")
	parser.add_option( "-f", "--font", dest="font_type", help="Font type", type="string", default="Bitstream Vera Sans" )
	parser.add_option( "--font-size", dest="font_size", help="Font size", type="int", default=9 )
	parser.add_option( "--doxygen", dest="doxygen", help="Generate Doxygen output", action="store_true", default=False)
	parser.add_option( "--doxygen-title", dest="doxygen_title", help="Title for the generated Doxygen page", default="Protocol Buffer Definition Map" )
	parser.add_option( "-T", dest="dot_output_format", help="Set additional output formats (passed as command-line argument to dot)", type="string", action="append")
	parser.add_option( "--dot", dest="dot", help="Graphviz directed graph generator (dot)", type="string", default="dot" )
	parser.add_option( "--plugin", dest="plugin", help="Use a plugin", type="string", default=None )
	parser.add_option( "-d", "--debug", dest="debug", help="Print debug info", action="store_true", default=False)
	

	(options, args) = parser.parse_args()

	logging.basicConfig( level = logging.DEBUG if options.debug else logging.INFO )

	if len(args) == 0:
		parser.print_help()
		sys.exit(1)

	if options.plugin is not None:
		options.plugin = os.path.realpath( options.plugin )

	o = Proto2Dot( options )

	if options.plugin is not None:
		context = {
			'parser': parser,
			'o': o,
			'self': o,
			'logging': logging,
		}
		execfile( options.plugin, context, context )

	proto_dir = os.getcwd()

	error = False
	for proto_filename in args:
		proto_filename_ = os.path.abspath( proto_filename )
		if options.debug:
			tmpdir = "/tmp/proto2dot"
			try:
				shutil.rmtree(tmpdir)
			except OSError:
				pass
			try:
				os.makedirs( tmpdir )
			except OSError:
				pass
		else:
			tmpdir = tempfile.mkdtemp( prefix = "proto2dot" )

		sys.path.append(tmpdir)

		os.chdir( proto_dir )
		cmd = [ options.protoc, proto_filename, "--python_out="+tmpdir ]
		
		if options.proto_path:
			for proto_path in options.proto_path:
				cmd.append("-I"+proto_path)

		logging.debug("executing protobuf compiler: %s" % (cmd,))

		subprocess.call( cmd )

		os.chdir( tmpdir )


		for filename in glob.glob( "*.py" ):
			module_name = os.path.splitext( filename )[0]
			logging.debug("loading module '%s'..." % (module_name,))
			m = importlib.import_module( module_name )

			try:
				for message in m.DESCRIPTOR.message_types_by_name.itervalues():
					o.process_message_class( message )

			except:
				logging.error("Error processing '%s', skipping: \n%s" % (module_name, traceback.format_exc(),))
				error = True
				break

	if not error:
		graph = o.generate_dot_graph()
	
		# Generate graphviz file
		dot_filename = proto_filename_+".dot"
	
		f = open(dot_filename, "wb")
		f.write( graph )
		f.close()
	
	
		if options.dot_output_format:
			cmd = [ options.dot, '-O', dot_filename ] + [ '-T'+x for x in options.dot_output_format ]
			logging.debug("executing graphviz: %s" % (cmd,))
	
			subprocess.call( cmd )
	
	
	
	
		if options.doxygen:
			# Generate Doxygen page
			f = open(proto_filename_+".dox", "wb")
			f.write("""/**
\page protobuf_map %(title)s

%(title)s
==================================

\dot
""" % {
	"title": options.doxygen_title,
})
			f.write( graph )
			f.write("""
\enddot

*/
""")
			f.close()

		error = False
		try:
			if options.plugin is not None and 'plugin_post' in context:
				context['plugin_post']()

		except:
			logging.error("Error running plugin: \n%s" % (traceback.format_exc(),))
			error = True

		if not error:
			for suffix, content in o.files.iteritems():
				if options.debug:
					logging.debug("writing file '%s'...\n", (proto_filename_+"."+suffix,) )
				f = open(proto_filename_+"."+suffix, "wb")
				if isinstance(content, (list, tuple) ):
					content = '\n'.join(content)
				f.write( content )
				f.close()

	sys.path.remove(tmpdir)
	if not options.debug:
		shutil.rmtree(tmpdir)

if __name__ == "__main__":
	sys.exit( main() )
