import sys
import os
import os.path
from texture import Texture




if __name__ == "__main__":
    if len(sys.argv) <= 1 or len(sys.argv) > 3:
        print("Usage:")
        print("   %s <file_in> [<file_out>]" % (sys.argv[0], ))
        print("Reads texture <file_in> and writes the contained image to a file. If <file_out> is given it will write the output to this, otherwise will extract the full contained path into the current directory.")
        exit(0)
    fh = open(sys.argv[1], "rb")
    tex = Texture()
    tex.loadFromFile(fh)
    fh.close()
    #print(sys.argv)
    if len(sys.argv) <= 2:
        fno = tex.filename
    else:
        fno = sys.argv[2]
    #create paths
    fno_path = os.path.dirname(fno)
    if not(os.path.exists(fno_path)):
        os.makedirs(fno_path)
    #write output file
    fho = open(fno, "wb")
    fho.write(tex.image_data)
    fho.close()
    print("Wrote: '%s'" % (fno, ))

