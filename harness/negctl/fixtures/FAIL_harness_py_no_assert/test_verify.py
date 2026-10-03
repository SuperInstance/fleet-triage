import subprocess


subprocess.run(['make', 'all'], check=True)
print('build verified')
