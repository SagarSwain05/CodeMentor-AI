"""Stdin-echo programs for every runnable language (used by tests and the matrix check).

Each program reads one line from stdin and prints "Hello, <line>!".
"""

RUN_SAMPLES = {
    "python": "name = input()\nprint(f'Hello, {name}!')\n",
    "javascript": "const lines = require('fs').readFileSync(0, 'utf8').split('\\n');\nconsole.log(`Hello, ${lines[0]}!`);\n",
    "typescript": "declare var require: any;\nconst name: string = require('fs').readFileSync(0, 'utf8').split('\\n')[0];\nconsole.log(`Hello, ${name}!`);\n",
    "java": "import java.util.Scanner;\npublic class Main {\n  public static void main(String[] a) {\n    Scanner s = new Scanner(System.in);\n    System.out.println(\"Hello, \" + s.nextLine() + \"!\");\n  }\n}\n",
    "c": "#include <stdio.h>\nint main(void) {\n  char b[64];\n  if (scanf(\"%63s\", b) == 1) printf(\"Hello, %s!\\n\", b);\n  return 0;\n}\n",
    "cpp": "#include <iostream>\n#include <string>\nint main() {\n  std::string n;\n  std::getline(std::cin, n);\n  std::cout << \"Hello, \" << n << \"!\" << std::endl;\n}\n",
    "csharp": "using System;\nclass Program {\n  static void Main() {\n    Console.WriteLine(\"Hello, \" + Console.ReadLine() + \"!\");\n  }\n}\n",
    "go": "package main\n\nimport (\n\t\"bufio\"\n\t\"fmt\"\n\t\"os\"\n\t\"strings\"\n)\n\nfunc main() {\n\tr := bufio.NewReader(os.Stdin)\n\tn, _ := r.ReadString('\\n')\n\tfmt.Printf(\"Hello, %s!\\n\", strings.TrimSpace(n))\n}\n",
    "rust": "use std::io;\nfn main() {\n    let mut n = String::new();\n    io::stdin().read_line(&mut n).unwrap();\n    println!(\"Hello, {}!\", n.trim());\n}\n",
    "kotlin": "fun main() {\n    val n = readLine() ?: \"\"\n    println(\"Hello, $n!\")\n}\n",
    "swift": "let n = readLine() ?? \"\"\nprint(\"Hello, \\(n)!\")\n",
    "ruby": "n = gets.to_s.strip\nputs \"Hello, #{n}!\"\n",
    "php": "<?php\n$n = trim(fgets(STDIN));\necho \"Hello, $n!\\n\";\n",
    "scala": "object Main {\n  def main(args: Array[String]): Unit = {\n    val n = scala.io.StdIn.readLine()\n    println(s\"Hello, $n!\")\n  }\n}\n",
    "dart": "import 'dart:io';\nvoid main() {\n  final n = stdin.readLineSync() ?? '';\n  print('Hello, $n!');\n}\n",
    "lua": "local n = io.read('*l')\nprint('Hello, ' .. n .. '!')\n",
    "perl": "my $n = <STDIN>;\nchomp $n;\nprint \"Hello, $n!\\n\";\n",
    "r": "con <- file('stdin')\nn <- readLines(con, n = 1)\nclose(con)\ncat(paste0('Hello, ', n, '!\\n'))\n",
    "julia": "n = readline()\nprintln(\"Hello, $(n)!\")\n",
    "haskell": "main :: IO ()\nmain = do\n  n <- getLine\n  putStrLn (\"Hello, \" ++ n ++ \"!\")\n",
    "elixir": "n = IO.gets(\"\") |> String.trim()\nIO.puts(\"Hello, #{n}!\")\n",
    "bash": "read n\necho \"Hello, $n!\"\n",
    "zig": "const std = @import(\"std\");\npub fn main() !void {\n    std.debug.print(\"Hello, World!\\n\", .{});\n}\n",
    "ocaml": "let () =\n  let n = read_line () in\n  Printf.printf \"Hello, %s!\\n\" n\n",
    "clojure": "(let [n (read-line)] (println (str \"Hello, \" n \"!\")))\n",
    "fortran": "program hello\n  character(len=64) :: n\n  read(*,'(A)') n\n  print '(A)', 'Hello, '//trim(n)//'!'\nend program hello\n",
    "groovy": "def n = System.in.newReader().readLine()\nprintln \"Hello, ${n}!\"\n",
    "sql": "SELECT 'Hello, ' || 'World' || '!';\n",
    "objectivec": "#import <stdio.h>\nint main(void) {\n  char b[64];\n  if (scanf(\"%63s\", b) == 1) printf(\"Hello, %s!\\n\", b);\n  return 0;\n}\n",
    "erlang": "-module(prog).\n-export([main/1]).\nmain(_) ->\n    N = string:trim(io:get_line(\"\")),\n    io:format(\"Hello, ~s!~n\", [N]).\n",
    "fsharp": "let n = stdin.ReadLine()\nprintfn \"Hello, %s!\" n\n",
    "powershell": "$n = $input | Select-Object -First 1\nWrite-Output \"Hello, $n!\"\n",
}

# Languages whose sample doesn't read stdin (prints a fixed greeting)
FIXED_OUTPUT = {"zig": "Hello, World!", "sql": "Hello, World!"}
