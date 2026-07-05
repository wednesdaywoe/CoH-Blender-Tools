import os.path
import os
import sys
from texture import Texture


#todo:

if __name__ == "__main__":
    if len(sys.argv) <= 1 or len(sys.argv) > 4:
        print("Usage:")
        print("   %s <file_in> [<file_out> [<texture_name>]]" % (sys.argv[0], ))
        print("Puts a .dds file inside a .texture file.")
        print("<file_out> will default to the same name but with a .texture extension.")
        print("<texture_name> will defaul to <file_in> starting 'texture_library'.")
        exit(0)
    filename_in = sys.argv[1].replace("\\", "/")
    fh = open(filename_in, "rb")
    image_data = fh.read()
    fh.close()

    #print("filename_in: '%s'" % (filename_in, )) 

    filedir_in = os.path.dirname(filename_in)
    if "texture_library" in filedir_in.split("/"):
        context_name = filename_in[filedir_in.find("texture_library"):]
    else:
        #todo: warning about not being in the texture_library heirachy?
        context_name = filename_in
    #print("context_name: '%s'" % (context_name, )) 

    if len(sys.argv) >= 4:
        context_name = sys.argv[3].replace("\\", "/")
        #todo: check input and output extensions match
    #print("context_name: '%s'" % (context_name, )) 
    if len(sys.argv) >= 3:
        filepath_out = sys.argv[2].replace("\\", "/")
        if filepath_out[-1] == "/" or (os.path.exists(filepath_out) and os.path.isdir(filepath_out)):
            if filepath_out[-1] == "/":
                if not os.path.exists(filepath_out):
                    os.makedirs(filepath_out)
            filename_out = os.path.join(filepath_out, os.path.splitext(context_name)[0] + ".texture")
        else:
            filename_out = filepath_out
    else:
        filename_out = os.path.splitext(context_name)[0] + ".texture"
    filedir_out = os.path.dirname(filename_out)
    if not os.path.exists(filedir_out):
        os.makedirs(filedir_out)
    
    #print("filename_out: '%s'" % (filename_out, )) 

    texture = Texture()
    texture.filename = bytes(context_name, "utf-8")
    texture.setImageData(image_data)

    data = texture.saveToData()

    texture.dump()

    fh_out = open(filename_out, "wb")
    fh_out.write(data)
    fh_out.close()
