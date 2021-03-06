import sys
from future.utils import iteritems
import os
from os.path import join as pjoin
from setuptools import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext
import subprocess
import numpy


## ref : https://github.com/rmcgibbo/npcuda-example/blob/master/cython/setup.py
def find_in_path(name, path):
    "Find a file in a search path"
    #adapted fom http://code.activestate.com/recipes/52224-find-a-file-given-a-search-path/
    for dir in path.split(os.pathsep):
        binpath = pjoin(dir, name)
        if os.path.exists(binpath):
            return os.path.abspath(binpath)
    return None


## ref : https://github.com/rmcgibbo/npcuda-example/blob/master/cython/setup.py
def locate_cuda():
    """Locate the CUDA environment on the system

    Returns a dict with keys 'home', 'nvcc', 'include', and 'lib64'
    and values giving the absolute path to each directory.

    Starts by looking for the CUDA_ROOT env variable. If not found, everything
    is based on finding 'nvcc' in the PATH.
    """

    # first check if the CUDAHOME env variable is in use
    if 'CUDA_ROOT' in os.environ:
        home = os.environ['CUDA_ROOT']
        nvcc = pjoin(home, 'bin', 'nvcc')
    else:
        # otherwise, search the PATH for NVCC
        nvcc = find_in_path('nvcc', os.environ['PATH'])
        if nvcc is None:
            raise EnvironmentError('The nvcc binary could not be '
                'located in your $PATH. Either add it to your path, or set $CUDA_ROOT')
        home = os.path.dirname(os.path.dirname(nvcc))

    cudaconfig = {'home':home, 'nvcc':nvcc,
                  'include': pjoin(home, 'include'),
                  'lib64': pjoin(home, 'lib64')}
    for k, v in iteritems(cudaconfig):
        if not os.path.exists(v):
            raise EnvironmentError('The CUDA %s path could not be located in %s' % (k, v))

    return cudaconfig


## ref : https://github.com/rmcgibbo/npcuda-example/blob/master/cython/setup.py
def customize_compiler_for_nvcc(self):
    """inject deep into distutils to customize how the dispatch
    to gcc/nvcc works.

    If you subclass UnixCCompiler, it's not trivial to get your subclass
    injected in, and still have the right customizations (i.e.
    distutils.sysconfig.customize_compiler) run on it. So instead of going
    the OO route, I have this. Note, it's kindof like a wierd functional
    subclassing going on."""

    # tell the compiler it can processes .cu
    self.src_extensions.append('.cu')

    # save references to the default compiler_so and _comple methods
    default_compiler_so = self.compiler_so
    super = self._compile

    # now redefine the _compile method. This gets executed for each
    # object but distutils doesn't have the ability to change compilers
    # based on source extension: we add it.
    def _compile(obj, src, ext, cc_args, extra_postargs, pp_opts):
        if os.path.splitext(src)[1] == '.cu':
            # use the cuda for .cu files
            self.set_executable('compiler_so', CUDA['nvcc'])
            # use only a subset of the extra_postargs, which are 1-1 translated
            # from the extra_compile_args in the Extension class
            postargs = extra_postargs['nvcc']
        else:
            postargs = extra_postargs['gcc']

        super(obj, src, ext, cc_args, postargs, pp_opts)
        # reset the default compiler_so, which we might have changed for cuda
        self.compiler_so = default_compiler_so

    # inject our redefined _compile method into the class
    self._compile = _compile


## ref : https://github.com/rmcgibbo/npcuda-example/blob/master/cython/setup.py
# run the customize_compiler
class custom_build_ext(build_ext):
    def build_extensions(self):
        customize_compiler_for_nvcc(self.compiler)
        build_ext.build_extensions(self)



CUDA = locate_cuda()

# Obtain the numpy include directory.  This logic works across numpy versions.
try:
    numpy_include = numpy.get_include()
except AttributeError:
    numpy_include = numpy.get_numpy_include()



ext = [# Extension('src/pose_estimator',
       #           sources=[
       #               'cuda/evaluate_gpu.cu',
       #               'src/pose_estimator.cpp',
       #               'src/shader.cpp',
       #               'src/Mesh.cpp',
       #                ],
       #           library_dirs=[CUDA['lib64']],
       #           libraries=['cudart', 'assimp', 'glfw', 'GLEW'],
       #           language='c++',
       #           runtime_library_dirs=[CUDA['lib64']],
       #           extra_compile_args={'gcc': ['-c', '-O3', '-std=c++11'],
       #                               'nvcc': ['-arch=sm_50',
       #                                        '--ptxas-options=-v','-O3',
       #                                        '-std=c++11',
       #                                        '-c', '--compiler-options', "'-fPIC'"]},
       #           extra_link_args=[],
       #           include_dirs = [numpy_include, '/usr/include/eigen3',
       #                           CUDA['include'], '.'],
       #       ),
       Extension('pose_estimation',
                 sources=['src/model_base_ransac_estimation.pyx',
                          'cuda/evaluate_gpu.cu',
                          'src/pose_estimator.cpp',
                          'src/shader.cpp',
                          'src/Mesh.cpp',],
                 library_dirs=[CUDA['lib64']],
                 libraries=['cudart', 'assimp', 'glfw', 'GLEW'],
                 language='c++',
                 runtime_library_dirs=[CUDA['lib64']],
                 extra_compile_args={'gcc': ['-c', '-O3', '-std=c++11'],
                                     'nvcc': ['-arch=sm_50',
                                              '--ptxas-options=-v','-O3',
                                              '-std=c++11',
                                              '-c', '--compiler-options', "'-fPIC'"]},
                 # extra_link_args=['src/pose_estimator.so',],
                 include_dirs = [numpy_include, '/usr/include/eigen3',
                                 CUDA['include'], 'include', '.'],
             ),
   ]

setup(
    name = "pose_estimation_gpu",
    author = 'Yusuke Oshiro',
    author_email='oshiroy0501@gmail.com',
    description = 'RANSAC-Based Pose Estimation using GPU',
    ext_modules = ext,
    # inject our custom trigger
    cmdclass={'build_ext': custom_build_ext},
    # since the package has c code, the egg cannot be zipped
    zip_safe=False)
