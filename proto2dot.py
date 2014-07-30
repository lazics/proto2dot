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

__version__	= "1.0"
__author__	= "Laszlo Bako-Szabo"
__email__	= "lazics@gmail.com"
__license__	= "GPLv3"

def main():
	from optparse import OptionParser

	parser = OptionParser()
	parser.usage = "usage: %prog [options] "

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

		output = {
			'nodes': {},
			'connections': [],
		}

		for filename in glob.glob( "*.py" ):
			module_name = os.path.splitext( filename )[0]
			logging.debug("loading module '%s'..." % (module_name,))
			m = importlib.import_module( module_name )

			try:

				for n in dir(m):
					if n[0]=='_':
						continue
					cls = getattr(m, n)
					if not isinstance( cls, m._reflection.GeneratedProtocolMessageType ):
						continue

					logging.debug("found class %s" % (cls,))
					
					descr = cls.DESCRIPTOR
					
					field_types_by_value={}
					
					for field_descr_n, field_descr_v in m._descriptor.FieldDescriptor.__dict__.iteritems():
						if not field_descr_n.startswith('TYPE_'):
							continue
						field_types_by_value[ field_descr_v ] = field_descr_n[ 5 : ].lower()

					output["nodes"][ n ]="""
	%(name)s [
		shape = plaintext
		label = """ % {
	"name": n,
}

					output["nodes"][ n ]+="<<TABLE BORDER=\"0\" CELLBORDER=\"1\" CELLSPACING=\"0\" ALIGN=\"LEFT\" VALIGN=\"TOP\"><TR><TD COLSPAN=\"4\"><B>"+ n +"</B></TD></TR>"

					for field in descr.fields:
						field_name = field.name
						output["nodes"][ n ] += "<TR>"

						# field number
						output["nodes"][ n ] += "<TD>"+ str(field.number) +"</TD>" 

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

						output["nodes"][ n ] += "<TD TITLE=\""+ mult_str +"\">" + mult + "</TD>"
						
						# field type
						output["nodes"][ n ] +=	"<TD ALIGN=\"LEFT\"><FONT COLOR=\"#444444\">&lt;" + field_types_by_value[ field.type ] + "&gt;</FONT></TD>"
						
						# field name with connection port
						output["nodes"][ n ] +=	"<TD ALIGN=\"LEFT\" PORT=\"l_" + field_name + "\">"
						

						if field.type == field.TYPE_ENUM:
							# enum field, display a list of values
							output["nodes"][ n ] += "<TABLE BORDER=\"0\" CELLBORDER=\"0\" CELLSPACING=\"0\"  ALIGN=\"LEFT\" VALIGN=\"TOP\"><TR><TD COLSPAN=\"3\" ALIGN=\"LEFT\">"+ field_name +"</TD></TR>"
							for e in field.enum_type.values:
								output["nodes"][ n ] += "<TR><TD WIDTH=\"10\"></TD><TD ALIGN=\"LEFT\"><FONT POINT-SIZE=\""+ str(options.font_size - 2) +"\">["+ str(e.number) +"]</FONT></TD><TD ALIGN=\"LEFT\"><I><FONT POINT-SIZE=\""+ str(options.font_size - 2) +"\">"+ e.name +"</FONT></I></TD></TR>"
							output["nodes"][ n ] += "</TABLE>"
						else:
							# not an enum, just display the name
							output["nodes"][ n ] += field_name
						output["nodes"][ n ] += "</TD>"


						# reference to another message
						if field.type == field.TYPE_MESSAGE:
							output["connections"].append( "\t\t"+ n +":l_"+ field_name + " -> " + field.message_type.name )
							
						output["nodes"][ n ] += "</TR>"


					output["nodes"][ n ]+="</TABLE>>"

					output["nodes"][ n ]+="""
	]
""" % {
	"name": n,
}
			except:
				logging.error("Error processing '%s', skipping: \n%s" % (module_name, traceback.format_exc(),))

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
	"font_type": options.font_type,
	"font_size": options.font_size,
})

		f.write( '\n'.join(output["nodes"].values()) )
		f.write( '\n'.join(output["connections"]) )

		f.write( """
}
""")
		graph = f.getvalue()
		f.close()


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
