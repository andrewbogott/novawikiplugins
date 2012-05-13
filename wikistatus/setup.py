# Copyright 2012 Andrew Bogott for the Wikimedia Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import setuptools

requirements = ["mwclient"]

setuptools.setup(
    name="openstack-wikistatus",
    version="2012.6",
    author="Wikimedia Foundation",
    author_email="abogott@wikimedia.org",
    description="Nova plugin that posts live instance status to a wiki page",
    long_description="Loooooooooooong description.  Super long.",
    license="Apache License, Version 2.0",
    url="https://github.com/andrewbogott/novawikiplugins",
    packages=setuptools.find_packages(exclude=['tests', 'tests.*']),
    install_requires=requirements,
    tests_require=["nose", "mock"],
    test_suite="nose.collector",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python"
    ],
    entry_points={
        "nova.plugin": ["plugin=wikistatus.wikistatus:StatusPlugin"]
    },
    py_modules=[]
)
