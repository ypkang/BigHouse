#!/usr/bin/env python
# try differen util to get to the target average latency

import sys
import csv
# Copied from tplocal.py
import jpype
import os.path

# import jar files
jarpath = os.path.abspath('.')
jpype.startJVM(jpype.getDefaultJVMPath(), "-Djava.ext.dirs=%s" % jarpath)

# import java packages
java = jpype.JPackage('java')
core = jpype.JPackage('core')
datacenter = jpype.JPackage('datacenter')
generator = jpype.JPackage('generator')
math = jpype.JPackage('math')
stat = jpype.JPackage('stat') 
StatName = jpype.JClass('core.Constants$StatName')
SocketPowerPolicy = jpype.JClass('datacenter.Socket$SocketPowerPolicy')
CorePowerPolicy = jpype.JClass('datacenter.Core$CorePowerPolicy')

# global stat requirements for statistical convergence
meanPrecision = .05
quantileSetting = .95
quantilePrecision = .05
warmupSamples = 5000

# scaled QPS, will be updated by createExperiment
scaledQps = 0.0

# this function creates an experiment
# adapted from powercaplocal.py
def createExperiment(targetRho, arrivalFile, serviceFile):

  global meanPrecision, quantileSetting, quantilePrecision, warmupSamples
  
  # service file
  # arrivalFile = "workloads/search-trunc.arrival.cdf"
  # serviceFile = "workloads/search-trunc.service.cdf"

  #specify distribution
  cores = 1
  sockets = 1
  # targetRho = 0.5
  print "target util " + str(targetRho)

  arrivalDistribution = math.EmpiricalDistribution.loadDistribution(arrivalFile, 1.0)
  serviceDistribution = math.EmpiricalDistribution.loadDistribution(serviceFile, 1.0)

  averageInterarrival = arrivalDistribution.getMean()
  averageServiceTime = serviceDistribution.getMean()
  qps = 1/averageInterarrival
  rho = qps/(cores*(1/averageServiceTime))
  arrivalScale = rho/targetRho
  averageInterarrival = averageInterarrival*arrivalScale
  serviceRate = 1/averageServiceTime
  # scaledQps = (qps/arrivalScale)
  global scaledQps 
  scaledQps = (qps/arrivalScale)

  # debug output
# print "Cores: %s" % cores
# print "rho: %s" % rho
# print "recalc rho: %s" % (scaledQps/(cores*(1/averageServiceTime)))
# print "arrivalScale: %s" % arrivalScale
# print "Average interarrival time: %s" % averageInterarrival
# print "QPS as is %s" % qps
# print "Scaled QPS: %s" % scaledQps
# print "Service rate as is %s" % serviceRate
# print "Service rate x: %s" % cores + " is: %s" % ((serviceRate)*cores)
# print "\n------------------\n"
# setup experiment
  experimentInput = core.ExperimentInput()

  rand = generator.MTRandom(long(1))
  arrivalGenerator = generator.EmpiricalGenerator(rand, arrivalDistribution, "arrival", arrivalScale)
  serviceGenerator = generator.EmpiricalGenerator(rand, serviceDistribution, "service", 1.0)

  # add experiment outputs
  experimentOutput = core.ExperimentOutput()
  experimentOutput.addOutput(StatName.SOJOURN_TIME, meanPrecision, quantileSetting, quantilePrecision, warmupSamples)
  # experimentOutput.addOutput(StatName.SERVER_LEVEL_CAP, meanPrecision, quantileSetting, quantilePrecision, warmupSamples)
  experiment = core.Experiment("Throughput experiment", rand, experimentInput, experimentOutput)

  #setup datacenter 
  dataCenter = datacenter.DataCenter()

  nServers = 1  
  capPeriod = 1.0
  globalCap = 65.0 * nServers
  maxPower = 100.0 * nServers
  minPower = 59.0 * nServers
  # enforcer = datacenter.PowerCappingEnforcer(experiment, capPeriod, globalCap, maxPower, minPower)
  for i in range(0, nServers):
    server = datacenter.Server(sockets, cores, experiment, arrivalGenerator, serviceGenerator)

    server.setSocketPolicy(SocketPowerPolicy.NO_MANAGEMENT)
    server.setCorePolicy(CorePowerPolicy.NO_MANAGEMENT) 
    coreActivePower = 40 * (4.0/5)/cores
    coreIdlePower = coreActivePower*0.2
    coreParkPower = 0.0

    socketActivePower = 40 * (1.0/5)/sockets
    socketParkPower = 0.0

    server.setCoreActivePower(coreActivePower)
    server.setCoreParkPower(coreParkPower)
    server.setCoreIdlePower(coreIdlePower)

    server.setSocketActivePower(socketActivePower)
    server.setSocketParkPower(socketParkPower)
    # enforcer.addServer(server)
    dataCenter.addServer(server)
    
  experimentInput.setDataCenter(dataCenter)
  
  return experiment

### MAIN ####
target_mean = 0.15
networks = ['wifi', 'lte', '3g']
cpu_percentage = [0, 30, 70, 100]
methods = ['sq', 'ns']

outcsv = "result/server-tp.csv"
writer = csv.writer(open(outcsv, 'wb'), delimiter=",")
writer.writerow(['network', 'cpu%', 'gpu%', 'method', 'scaledQPS'])

for net in networks:
  for cpu_per in cpu_percentage:
    for met in methods:
      # first experiment with rho=0.5
      minRho = 0.0
      maxRho = 1.0
      arrivalFile = "workloads/search.arrival.cdf"
      serviceFile = "/home/ypkang/git/neurosurgeon/service-distro/cdfs/%s-cpu%d-gpu%d-%s.service.cdf" % (net, cpu_per, 100-cpu_per, met)
      print "service cdf file: " + serviceFile
      
      while(1):
        currentRho = (minRho + maxRho)/2.0
        
        experiment = createExperiment(float(currentRho), arrivalFile, serviceFile)
        experiment.run()
        responseTimeMean = experiment.getStats().getStat(StatName.SOJOURN_TIME).getAverage()
        
        if responseTimeMean < target_mean * (1.0-meanPrecision):
          minRho = currentRho
        elif responseTimeMean > target_mean * (1.0+meanPrecision):
          maxRho = currentRho
        else:
          # bingo! 
          print "arrive at the target mean latency"
          print "Final scaledQPS: %s" % (scaledQps)
          break
      # write to csv
      writer.writerow([net, cpu_per, 100-cpu_per, met, scaledQps])
    
# print "====== Final Results ======"
# responseTimeMean = experiment.getStats().getStat(StatName.SOJOURN_TIME).getAverage()
# print "SOJOURN_TIME mean : %s" % responseTimeMean
# responseTimeQuantile = experiment.getStats().getStat(StatName.SOJOURN_TIME).getQuantile(quantileSetting)
# print "%s quantile SOJOURN_TIME : %s" % (quantileSetting, responseTimeQuantile)
# print "Scaled QPS: %s" % (scaledQps)
# 
