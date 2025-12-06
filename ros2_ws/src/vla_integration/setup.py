from setuptools import setup
import os
from glob import glob

package_name = 'vla_integration'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Include all launch files
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='user',
    maintainer_email='user@example.com',
    description='Vision-Language-Action integration package for robotics',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'speech_recognition_node = vla_integration.speech_recognition_node:main',
            'llm_planning_service = vla_integration.llm_planning_service:main',
            'vision_node = vla_integration.vision_node:main',
        ],
    },
)