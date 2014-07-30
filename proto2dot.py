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

from google.protobuf import descriptor
from google.protobuf import reflection

__version__	= "1.0"
__author__	= "Laszlo Bako-Szabo"
__email__	= "lazics@gmail.com"
__license__	= "GPLv3"

class Proto2Dot(object):
	output = None
	tree = None

	def __init__(self, options):
		self.options = options

		self.output = {
			'nodes': {},
			'connections': [],
		}

		self.tree = {
			'name': None,
			'name_long': None,
			'label': None,
			'path': [],
			'parent': None,
			'children': {},
			'links': {},
		}

		self.field_types_by_value={}

		for field_descr_n, field_descr_v in descriptor.FieldDescriptor.__dict__.iteritems():
			if not field_descr_n.startswith('TYPE_'):
				continue
			self.field_types_by_value[ field_descr_v ] = field_descr_n[ 5 : ].lower()

	def find_leaf(self, branch):
		def _find_leaf(branch):
			if ( len(branch)==0 ): 
				return self.tree
			if ( len(branch)==1 ): 
				return self.tree['children'][ branch[0] ]
			else:
				return _find_leaf( self.tree[ branch[0] ]['children'] )
		return _find_leaf( copy.deepcopy( branch ) )

	def rfind_leaf_by_name(self, branch, name):
		if name in branch['children']:
			return branch['children'][name]

		if branch['parent'] is None:
			return None
		if branch['parent']['name'] == name:
			return branch['parent']
		else:
			return self.rfind_leaf_by_name( branch['parent'], name ) 

	def process_message_class(self, cls, branch_path):
		logging.debug("processing message class %s" % (cls,))

		descr = cls.DESCRIPTOR
		n = '__'.join( branch_path + [ descr.name ])

		parent_leaf = self.find_leaf( branch_path )
		leaf = {
			'name': descr.name,
			'name_long': n,
			'label': ' &gt; '.join( branch_path + [ descr.name ]),
			'path': branch_path + [ descr.name ],
			'parent': parent_leaf,
			'children': {},
			'links': {},
		}
		parent_leaf['children'][ descr.name ] = leaf

		self.output["nodes"][ n ]="""
	%(name)s [
		shape = plaintext
		label = """ % {
	"name": n,
}

		self.output["nodes"][ n ]+="<<TABLE BORDER=\"0\" CELLBORDER=\"1\" CELLSPACING=\"0\" ALIGN=\"LEFT\" VALIGN=\"TOP\"><TR><TD COLSPAN=\"4\"><B>"+ leaf[ 'label' ] +"</B></TD></TR>"

		for field in descr.fields:
			field_name = field.name
			self.output["nodes"][ n ] += "<TR>"

			# field number
			self.output["nodes"][ n ] += "<TD>"+ str(field.number) +"</TD>" 

			# field multiplicity
			if field.label == field.LABEL_REQUIRED:
				mult = '[1..1]'
				mult_str = "required"
			if field.label == field.LABEL_OPTIONAL:
				mult = '[0..1]'
				mult_str = "optional"
			if field.label == field.LABEL_REPEATED:
				mult = '[0..n]'
				mult_str = "repeated"

			self.output["nodes"][ n ] += "<TD TITLE=\""+ mult_str +"\">" + mult + "</TD>"

			# field type
			self.output["nodes"][ n ] +=	"<TD ALIGN=\"LEFT\"><FONT COLOR=\"#444444\">&lt;" + self.field_types_by_value[ field.type ] + "&gt;</FONT></TD>"

			# field name with connection port
			self.output["nodes"][ n ] +=	"<TD ALIGN=\"LEFT\" PORT=\"l_" + field_name + "\">"


			if field.type == field.TYPE_ENUM:
				# enum field, display a list of values
				self.output["nodes"][ n ] += "<TABLE BORDER=\"0\" CELLBORDER=\"0\" CELLSPACING=\"0\"  ALIGN=\"LEFT\" VALIGN=\"TOP\"><TR><TD COLSPAN=\"3\" ALIGN=\"LEFT\">"+ field_name +"</TD></TR>"
				for e in field.enum_type.values:
					self.output["nodes"][ n ] += "<TR><TD WIDTH=\"10\"></TD><TD ALIGN=\"LEFT\"><FONT POINT-SIZE=\""+ str(self.options.font_size - 2) +"\">["+ str(e.number) +"]</FONT></TD><TD ALIGN=\"LEFT\"><I><FONT POINT-SIZE=\""+ str(self.options.font_size - 2) +"\">"+ e.name +"</FONT></I></TD></TR>"
				self.output["nodes"][ n ] += "</TABLE>"
			else:
				# not an enum, just display the name
				self.output["nodes"][ n ] += field_name
			self.output["nodes"][ n ] += "</TD>"


			# reference to another message
			if field.type == field.TYPE_MESSAGE:
				leaf["links"][ field_name ] = field.message_type.name

			self.output["nodes"][ n ] += "</TR>"


		self.output["nodes"][ n ]+="</TABLE>>"

		self.output["nodes"][ n ]+="""
	]
""" % {
	"name": n,
}

	def generate_links(self, branch = None):
		if branch is None:
			branch = self.tree
		for link_source, link_target in branch['links'].iteritems():

			link_target_leaf = self.rfind_leaf_by_name( branch, link_target )

			if link_target_leaf is None:
				logging.error("Can't find '%s'" % (link_target,))
			else:
				self.output["connections"].append( "\t\t"+ branch['name'] +":l_"+ link_source + " -> " + link_target_leaf["name_long"] )

		for child in branch['children'].itervalues():
			self.generate_links( child )

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
	parser.add_option( "-f", "--font", dest="font_type", help="Font type", type="string", default="Bitstream Vera Sans" )
	parser.add_option( "--font-size", dest="font_size", help="Font size", type="int", default=9 )
	parser.add_option( "--doxygen", dest="doxygen", help="Generate Doxygen output", action="store_true", default=False)
	parser.add_option( "--doxygen-title", dest="doxygen_title", help="Title for the generated Doxygen page", default="Protocol Buffer Definition Map" )
	parser.add_option( "-T", dest="dot_output_format", help="Set additional output formats (passed as command-line argument to dot)", type="string", action="append")
	parser.add_option( "--dot", dest="dot", help="Graphviz directed graph generator (dot)", type="string", default="dot" )
	parser.add_option( "-d", "--debug", dest="debug", help="Print debug info", action="store_true", default=False)
	

	(options, args) = parser.parse_args()

	logging.basicConfig( level = logging.DEBUG if options.debug else logging.INFO )

	if len(args) == 0:
		parser.print_help()
		sys.exit(1)

	o = Proto2Dot( options )

	proto_dir = os.getcwd()

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

				def _search_for_message_classes(ctx, branch_path = None):
					if branch_path is None:
						branch_path = []

					for n in dir(ctx):
						if n[0]=='_':
							continue
						cls = getattr(ctx, n)

						if not isinstance( cls, reflection.GeneratedProtocolMessageType ):
							continue

						o.process_message_class( cls, branch_path = branch_path )

						_search_for_message_classes(cls, branch_path = branch_path + [ n ])


				_search_for_message_classes(m)

			except:
				logging.error("Error processing '%s', skipping: \n%s" % (module_name, traceback.format_exc(),))

		#~ logging.debug("tree: \n%s" % (pprint.pformat(o.tree),))

		o.generate_links()

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
\page %(title)s

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

		sys.path.remove(tmpdir)
		if not options.debug:
			shutil.rmtree(tmpdir)

if __name__ == "__main__":
	sys.exit( main() )
