from subprocess import run

with open('requirements.txt','r') as f:
    libs = f.read().split('\n')
    for lib in libs:
        print('Installing/Upgrading '+lib)
        run(['pip','install','--upgrade',lib])
        print('Complete')