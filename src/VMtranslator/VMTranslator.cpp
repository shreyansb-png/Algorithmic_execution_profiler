#include <iostream>
#include <fstream>
#include <filesystem>
#include <vector>
#include <algorithm>
#include <string>
#include <sstream>

using namespace std;

class CodeWriter {
private:
    ofstream opfile;
    int jumpcounter;
    int callCounter;
    string fileName;
    string currentFunction;

public:
    CodeWriter(const string& filename) {
        opfile.open(filename + ".asm");
        jumpcounter = 0;
        callCounter = 0;
        fileName = filename;
        currentFunction = "";
    }

    ~CodeWriter() {
        if(opfile.is_open()) opfile.close();
    }

    void setFileName(const string& name) {
        fileName = name;
    }

    void writelnit() {
        opfile << "// Bootstrap code\n" 
               << "@256\n"
               << "D=A\n" 
               << "@SP\n" 
               << "M=D\n";
        writeCall("Sys.init", 0);
    }

    void writeArithmetic(const string& command) {
        if(command == "add") {
            opfile << "// add\n" 
                   << "@SP\nAM=M-1\nD=M\n" 
                   << "@SP\nAM=M-1\nM=M+D\n" 
                   << "@SP\nM=M+1\n";
        } else if(command == "sub") {
            opfile << "// sub\n" 
                   << "@SP\nAM=M-1\nD=M\n" 
                   << "@SP\nAM=M-1\nM=M-D\n" 
                   << "@SP\nM=M+1\n";
        } else if(command == "neg") {
            opfile << "// neg\n" 
                   << "@SP\nA=M-1\nM=-M\n";
        } else if(command == "eq" || command == "gt" || command == "lt") {
            string comp = (command == "eq") ? "JEQ" : (command == "gt") ? "JGT" : "JLT";
            string labeltrue = "COMP_TRUE_" + to_string(jumpcounter);
            string labelend = "COMP_END_" + to_string(jumpcounter);
            jumpcounter++;
            
            opfile << "// " << command << "\n" 
                   << "@SP\nAM=M-1\nD=M\n" 
                   << "@SP\nAM=M-1\nD=M-D\n" 
                   << "@" << labeltrue << "\nD;" << comp << "\n" 
                   << "@SP\nA=M\nM=0\n" 
                   << "@" << labelend << "\n0;JMP\n" 
                   << "(" << labeltrue << ")\n" 
                   << "@SP\nA=M\nM=-1\n" 
                   << "(" << labelend << ")\n" 
                   << "@SP\nM=M+1\n";
        } else if(command == "and") {
            opfile << "// and\n" 
                   << "@SP\nAM=M-1\nD=M\n" 
                   << "@SP\nAM=M-1\nM=M&D\n" 
                   << "@SP\nM=M+1\n";
        } else if(command == "or") {
            opfile << "// or\n" 
                   << "@SP\nAM=M-1\nD=M\n" 
                   << "@SP\nAM=M-1\nM=M|D\n" 
                   << "@SP\nM=M+1\n";
        } else if(command == "not") {
            opfile << "// not\n" 
                   << "@SP\nA=M-1\nM=!M\n";
        }
    }

    void writePushPop(const string& command, const string& segment, int idx) {
        if(command == "push") {
            if(segment == "constant") {
                opfile << "// push constant " << idx << "\n" 
                       << "@" << idx << "\nD=A\n"
                       << "@SP\nA=M\nM=D\n" 
                       << "@SP\nM=M+1\n";
            } else if(segment == "local" || segment == "argument" || segment == "this" || segment == "that") {
                string baseptr = (segment == "local") ? "LCL" : (segment == "argument") ? "ARG" : (segment == "this") ? "THIS" : "THAT";
                opfile << "// push " << segment << " " << idx << "\n" 
                       << "@" << idx << "\nD=A\n" 
                       << "@" << baseptr << "\nA=M+D\nD=M\n" 
                       << "@SP\nA=M\nM=D\n" 
                       << "@SP\nM=M+1\n";
            } else if(segment == "temp") {
                opfile << "// push temp " << idx << "\n" 
                       << "@" << (5 + idx) << "\nD=M\n" 
                       << "@SP\nA=M\nM=D\n" 
                       << "@SP\nM=M+1\n";
            } else if(segment == "pointer") {
                string addr = (idx == 0) ? "THIS" : "THAT";
                opfile << "// push pointer " << idx << "\n" 
                       << "@" << addr << "\nD=M\n"
                       << "@SP\nA=M\nM=D\n" 
                       << "@SP\nM=M+1\n";
            } else if(segment == "static") {
                opfile << "// push static " << idx << "\n" 
                       << "@" << fileName << "." << idx << "\nD=M\n" 
                       << "@SP\nA=M\nM=D\n"
                       << "@SP\nM=M+1\n";
            }
        } else if(command == "pop") {
            if(segment == "local" || segment == "argument" || segment == "this" || segment == "that") {
                string baseptr = (segment == "local") ? "LCL" : (segment == "argument") ? "ARG" : (segment == "this") ? "THIS" : "THAT";
                opfile << "// pop " << segment << " " << idx << "\n" 
                       << "@" << idx << "\nD=A\n" 
                       << "@" << baseptr << "\nD=M+D\n" 
                       << "@R13\nM=D\n" 
                       << "@SP\nM=M-1\nA=M\nD=M\n" 
                       << "@R13\nA=M\nM=D\n";
            } else if(segment == "temp") {
                opfile << "// pop temp " << idx << "\n" 
                       << "@SP\nM=M-1\nA=M\nD=M\n" 
                       << "@" << (5 + idx) << "\nM=D\n";
            } else if(segment == "pointer") {
                string addr = (idx == 0) ? "THIS" : "THAT";
                opfile << "// pop pointer " << idx << "\n" 
                       << "@SP\nM=M-1\nA=M\nD=M\n" 
                       << "@" << addr << "\nM=D\n";
            } else if(segment == "static") {
                opfile << "// pop static " << idx << "\n" 
                       << "@SP\nM=M-1\nA=M\nD=M\n" 
                       << "@" << fileName << "." << idx << "\nM=D\n";
            }
        }
    }

    void writeLabel(const string& label) {
        opfile << "(" << currentFunction << "$" << label << ")\n";
    }

    void writeGoto(const string& label) {
        opfile << "@" << currentFunction << "$" << label << "\n" 
               << "0;JMP\n";
    }

    void writelf(const string& label) {
        opfile << "@SP\nAM=M-1\nD=M\n" 
               << "@" << currentFunction << "$" << label << "\n" 
               << "D;JNE\n";
    }

    void writeFunction(const string& functionName, int numLocals) {
        currentFunction = functionName;
        opfile << "(" << functionName << ")\n";
        for(int i = 0; i < numLocals; ++i) {
            opfile << "@0\nD=A\n"
                   << "@SP\nA=M\nM=D\n" 
                   << "@SP\nM=M+1\n";
        }
    }

    void writeCall(const string& functionName, int numArgs) {
        string returnLabel = currentFunction + "$ret." + to_string(callCounter++);
        
        opfile << "@" << returnLabel << "\nD=A\n" 
               << "@SP\nA=M\nM=D\n" 
               << "@SP\nM=M+1\n";
        
        string segments[] = {"LCL", "ARG", "THIS", "THAT"};
        for(const string& seg : segments) {
            opfile << "@" << seg << "\nD=M\n" 
                   << "@SP\nA=M\nM=D\n" 
                   << "@SP\nM=M+1\n";
        }
        
        opfile << "@SP\nD=M\n" 
               << "@5\nD=D-A\n" 
               << "@" << numArgs << "\nD=D-A\n" 
               << "@ARG\nM=D\n";
        
        opfile << "@SP\nD=M\n" 
               << "@LCL\nM=D\n";
        
        opfile << "@" << functionName << "\n" 
               << "0;JMP\n";
        
        opfile << "(" << returnLabel << ")\n";
    }

    void writeReturn() {
        opfile << "@LCL\nD=M\n"
               << "@R13\nM=D\n";
               
        opfile << "@5\nD=A\n" 
               << "@R13\nA=M-D\nD=M\n" 
               << "@R14\nM=D\n";
               
        opfile << "@SP\nM=M-1\nA=M\nD=M\n" 
               << "@ARG\nA=M\nM=D\n";
               
        opfile << "@ARG\nD=M+1\n" 
               << "@SP\nM=D\n";
               
        opfile << "@1\nD=A\n" 
               << "@R13\nA=M-D\nD=M\n" 
               << "@THAT\nM=D\n";
               
        opfile << "@2\nD=A\n" 
               << "@R13\nA=M-D\nD=M\n" 
               << "@THIS\nM=D\n";
               
        opfile << "@3\nD=A\n" 
               << "@R13\nA=M-D\nD=M\n" 
               << "@ARG\nM=D\n";
               
        opfile << "@4\nD=A\n" 
               << "@R13\nA=M-D\nD=M\n" 
               << "@LCL\nM=D\n";
               
        opfile << "@R14\nA=M\n" 
               << "0;JMP\n";
    }
};

static void translateFile(CodeWriter& writer, const string& ipfile) {
    size_t lastdot = ipfile.find_last_of("/\\");
    string filenameWithExt = (lastdot != string::npos) ? ipfile.substr(lastdot + 1) : ipfile;
    size_t dot = filenameWithExt.find_last_of('.');
    string shortName = (dot != string::npos) ? filenameWithExt.substr(0, dot) : filenameWithExt;
    writer.setFileName(shortName);

    ifstream inFile(ipfile);
    if (!inFile.is_open()) {
        cout << "UNABLE TO OPEN FILE: " << ipfile << "\n";
        return;
    }

    string line;
    while (getline(inFile, line)) {
        size_t commentpos = line.find("//");
        if (commentpos != string::npos) line = line.substr(0, commentpos);

        stringstream ss(line);
        string command;
        if (!(ss >> command)) continue;

        if (command == "add" || command == "sub" || command == "neg" ||
            command == "eq" || command == "gt" || command == "lt" ||
            command == "and" || command == "or" || command == "not") {
            writer.writeArithmetic(command);
        } else if (command == "push" || command == "pop") {
            string segment; int idx;
            ss >> segment >> idx;
            writer.writePushPop(command, segment, idx);
        } else if (command == "label") {
            string label; ss >> label; writer.writeLabel(label);
        } else if (command == "goto") {
            string label; ss >> label; writer.writeGoto(label);
        } else if (command == "if-goto") {
            string label; ss >> label; writer.writelf(label);
        } else if (command == "function") {
            string fname; int n; ss >> fname >> n; writer.writeFunction(fname, n);
        } else if (command == "call") {
            string fname; int n; ss >> fname >> n; writer.writeCall(fname, n);
        } else if (command == "return") {
            writer.writeReturn();
        }
    }
}

int main(int argc, char* argv[]) {
    namespace fs = std::filesystem;
    string outName;
    vector<string> inputs;

    if (argc == 2 && fs::is_directory(argv[1])) {
        // Folder mode (used by benchmark.py): writes <folder>\<foldername>.asm
        fs::path dir = fs::absolute(argv[1]);
        if (dir.filename().empty()) dir = dir.parent_path();
        outName = (dir / dir.filename()).string();
        for (const auto& e : fs::directory_iterator(dir))
            if (e.path().extension() == ".vm") inputs.push_back(e.path().string());
        sort(inputs.begin(), inputs.end());
    } else if (argc >= 3) {
        // Original mode: VMTranslator out file1.vm file2.vm ...
        outName = argv[1];
        for (int i = 2; i < argc; ++i) inputs.push_back(argv[i]);
    } else {
        cout << "USAGE: VMTranslator <folder>\n"
                "   or: VMTranslator <out> <file1.vm> [file2.vm...]\n";
        return 1;
    }

    if (inputs.empty()) {
        cout << "No .vm files found.\n";
        return 1;
    }

    CodeWriter writer(outName);
    writer.writelnit();
    for (const string& f : inputs) translateFile(writer, f);

    cout << "Successfully generated " << outName << ".asm\n";
    return 0;
}