Proto2Dot
=========

Generate [GraphViz] files from [Google Protocol Buffer] definitions.

Author: Laszlo Bako-Szabo

Features
--------
- Parse [Google Protocol Buffer] definition files and create a map showing their relations.
- Generate [GraphViz] .dot file
- Generate [Doxygen] page
- Generate image files (everything supported by [GraphViz]

Usage
-----

$ proto2dot.py [options] <proto files>

	Options:
	  -h, --help            show this help message and exit
	  -o OUTPUT, --output=OUTPUT
	                        Output directory
	  -c PROTOC, --protoc=PROTOC
	                        Protocol buffer compiler
	  -I PROTO_PATH, --proto_path=PROTO_PATH
	                        directory in which to search for imports (passed as
	                        command-line argument to protoc)
	  -f FONT_TYPE, --font=FONT_TYPE
	                        Font type
	  --font-size=FONT_SIZE
	                        Font size
	  --doxygen             Generate Doxygen output
	  --doxygen-title=DOXYGEN_TITLE
	                        Title for the generated Doxygen page
	  -T DOT_OUTPUT_FORMAT  Set additional output formats (passed as command-line
	                        argument to dot)
	  --dot=DOT             Graphviz directed graph generator (dot)
	  -d, --debug           Print debug info


[GraphViz]: http://www.graphviz.org/
[Google Protocol Buffer]: https://code.google.com/p/protobuf/
[Doxygen]: http://www.doxygen.org/

