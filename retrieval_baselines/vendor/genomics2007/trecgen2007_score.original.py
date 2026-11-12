# trecgen2007_score.py
# Scoring program for the NIST TREC 2007 Genomics Track
# Includes new individual character as document passage measure PASSAGE2.
# Old measure is PASSAGE.
# Calculation of PASSAGE2 has been independently verified with parallel implementation by Fabien Campagne.
# Usage: python trecgen2007_score.py [path-to-gold-standard-file] [glob-or-path-to-run-file] > STDOUT
import sys
import glob
import os.path

# turns debugging output on and off...
DEBUG_FLAG = False

# utility function for debugging...
def debug(s):
	if DEBUG_FLAG:
		sys.stderr.write("%s\n" % s)
		
# function to remove duplicate elements from a list 
# this function must preserve order!
def removeDups(s):
	temp = set()
	out = []
	for t in s:
		if t not in temp:
			temp.add(t) 
			out.append(t) # Add the non-duplicate element to the output list while preserving the order
	return out

# function to read the run file and build the submission data structure.
# this is a dictionary of topics, each entry consisting of a list of ranked nominated passages...
def buildSubmissions(file):
	submissionDx = {}
	for line in file:
		# strip newline...
		line = line.strip()
		# skip blank lines...
		if len(line) == 0:
			continue
		# split fields by whitespace, should split by tabs but so many entrants did not
		# follow the official format that splitting by whitespace is more reliable...
		fields = line.split()
		# catch errors...		
		try:
			topic	=	int(fields[0])
			pmid	=	fields[1]
			rank	=	int(fields[2])
			offset =	int(fields[4])
			length =	int(fields[5])			
			submissionDx.setdefault(topic,[]).append((rank, pmid, offset, length))
		except Exception, e:
			# report and terminate...
			sys.stderr.write("Unable to correct improperly formated line:\n%s\n" % line)
			sys.stderr.write("Parsed fields are %s\n" % str(fields))
			raise e
	return submissionDx

# function to read the gold standard file and build the gold standard data structure.
# this is a dictionary of topics, each entry consisting of a dictionary, keyed by PMID,
# where each PMID is associated with a list of gold standard passage triples that are
# (offset,length,aspects), where offset and length are integers and aspects is a list of MeSH terms...
def buildGoldStd(file):
	goldStdDx = {}
	for line in file:
		fields = [s.strip() for s in line.split('\t')]
		if len(fields) > 4:
			topic	=	int(fields[0])
			pmid	=	fields[1]
			offset =	int(fields[2])
			length =	int(fields[3])
			# aspects in the gold standard file are separated from each other by a '|' symbol...
			aspects = [s.strip() for s in fields[4].split('|')]
			topicDx = goldStdDx.setdefault(topic,{})
			pmidLst = topicDx.setdefault(pmid,[])
			pmidLst.append((offset,length,aspects))
	return goldStdDx

# function to find unique pmids for all topicids in a dictionary,
# it is important that this function preserves rank order!
def buildUniquePmidsByTopic(submissionDx):
	uniquePmidsByTopic = {}
	for topic in submissionDx.keys():
		quartets = submissionDx[topic]
		quartets.sort() #sort the list by rank, then by pmid, then offset and then by length
		tempLst = []
		for quartet in quartets:
			pmid	=	quartet[1] 
			tempLst.append(pmid)
		# remove duplications, preserving order...
		uniquePmidsByTopic[topic] = removeDups(tempLst)
	return uniquePmidsByTopic

# return a dictionary where the keys are topics and the values are the average precision for that topic...
def calculateDocAveragePrecision(submissionDx, goldStdDx):
	averagePrecisionByTopic = {}
	uniquePmidsByTopic = buildUniquePmidsByTopic(submissionDx)
	for topic in goldStdDx:
		goldPmids = goldStdDx[topic]
		pmids = uniquePmidsByTopic.get(topic, [])
		numerator	=	0
		denominator=	0
		sumPrecision = 0.0
		for pmid in pmids:
			denominator += 1
			if pmid in goldPmids:
				numerator += 1
				# accumulate precision at each point of recall...
				precision = float(numerator)/float(denominator)
				sumPrecision += precision
				debug("DOCUMENT TOPIC:%d RANK:%d PMID:%s => relevant, %d/%d = %0.8f" % (topic, denominator, pmid, numerator, denominator, precision))
			else:
				debug("DOCUMENT TOPIC:%d RANK:%d PMID:%s => not relevant" % (topic, denominator, pmid))
				pass
		# average, adding zeros for each pmid that was not retrieved...
		averagePrecisionByTopic[topic]  = sumPrecision/len(goldPmids)
	return averagePrecisionByTopic

def findRelevantCharsByTopic(quartet, topic):
	relevantOffset	=	0
	relevantLength =	0
	relevantAspects = None
	goldPassage = None
	(rank, pmid, runOffset, runLength) = quartet
	runEnd = runOffset + runLength
	goldTriplets = goldStdDx[topic].get(pmid, [])
	for goldTriplet in goldTriplets:
		(goldOffset, goldLength, goldAspects) = goldTriplet
		goldEnd = goldOffset + goldLength
		if runOffset >= goldOffset and runEnd <= goldEnd:
			# run is fully contained in gold passage...
			relevantOffset = runOffset
			relevantLength = runLength
		elif runOffset < goldOffset and runEnd <= goldEnd and runEnd >= goldOffset:
			# run starts before the gold and ends within the gold...
			relevantOffset = goldOffset
			relevantLength =  runEnd - goldOffset
		elif  runOffset >= goldOffset and runOffset <= goldEnd and runEnd > goldEnd:
			# run starts within the gold and ends beyond the gold...
			relevantOffset = runOffset
			relevantLength =  goldEnd - runOffset
		elif runOffset < goldOffset and runEnd > goldEnd:
			# run starts before the gold and ends after the gold...
			relevantOffset = goldOffset
			relevantLength = goldLength
		if relevantLength != 0:
			relevantAspects = goldAspects
			goldPassage = (pmid, goldOffset, goldLength)
			break
	return (relevantOffset, relevantLength, relevantAspects, goldPassage)

def checkSpanOverlap(span, relevantSpans):
	(pmid, runOffset, runLength) = span
	runEnd = runOffset + runLength
	relevantChars = 0
	for (quartPmid, quartOffset, quartLength) in relevantSpans:
		if pmid != quartPmid:
			continue
		quartEnd = quartOffset + quartLength
		if runOffset >= quartOffset and runEnd <= quartEnd:
			# run is fully contained in quart passage...
			relevantChars = runLength
		elif runOffset < quartOffset and runEnd <= quartEnd and runEnd >= quartOffset:
			# run starts before the quart and ends within the quart...
			relevantChars =  runEnd - quartOffset
		elif  runOffset >= quartOffset and runOffset <= quartEnd and runEnd > quartEnd:
			# run starts within the quart and ends beyond the quart...
			relevantChars =  quartEnd - runOffset
		elif runOffset < quartOffset and runEnd > quartEnd:
			# run starts before the quart and ends after the quart...
			relevantChars = quartLength
		if relevantChars != 0:
			break
	return relevantChars

# return a dictionary where the keys are topics and the values are the passage average precision for that topic...
def calculatePassageAveragePrecision(submissionDx, goldStdDx):
	averagePrecisionByTopic = {}	
	for topic in goldStdDx:
		quartets = submissionDx.get(topic, [])
		quartets.sort() #sort the list by rank, then by pmid, then offset and then by length
		numerator = 0
		denominator = 0
		sumPrecision = 0.0
		count = 0
		foundGoldTriplets = set() # keep track of gold passages found
		relevantSpans = []
		for quartet in quartets:
			(relevantOffset, relevantChars, relevantAspects, goldPassage) = findRelevantCharsByTopic(quartet,topic)
			denominator += quartet[3]
			if relevantChars > 0:
				## check for "double-retrieval" of gold passage characters...
				## ideally, these should be removed from scoring, but none of the top rated systems
				## did this, and the effect on scoring appears minor.
				##if goldPassage in foundGoldTriplets and checkSpanOverlap(quartet[1:], relevantSpans) > 0:
				##	sys.stderr.write("WARNING: Relevant passage characters retrieved more than once!\n")
				##relevantSpans.append((quartet[1], relevantOffset, relevantChars))
				# accumulate precision at each point of recall...
				count += 1
				numerator += relevantChars
				sumPrecision += float(numerator)/float(denominator)
				foundGoldTriplets.add(goldPassage)
				debug("PASSAGE TOPIC:%d SPAN:%s.%d.%d => relevant, %d of %d chars" % (topic, quartet[1], quartet[2], quartet[3], relevantChars, quartet[3]))
			else:
				pass
				debug("PASSAGE TOPIC:%d SPAN:%s.%d.%d => not relevant, %d chars" % (topic, quartet[1], quartet[2], quartet[3], quartet[3]))				
		# determine which gold standard passages where not retrieved...
		allGoldPassages = set()
		for pmid in goldStdDx[topic]:
			for (offset, length, aspects) in goldStdDx[topic][pmid]:
				allGoldPassages.add((pmid, offset, length))
		numZeros = len(allGoldPassages.difference(foundGoldTriplets))		
		# compute the average precision for the topic...
		averagePrecisionByTopic[topic] = sumPrecision/(count + numZeros)
		debug("PASSAGE TOPIC:%d RETRIEVED %d of %d RELEVANT PASSAGES" % (topic, count, count + numZeros))
	return averagePrecisionByTopic

def findUniqueAspectsByTopic(topic):
	uniqueAspectsByTopic = set()
	for pmid in goldStdDx[topic]:
		goldTriplets = goldStdDx[topic][pmid]
		for (offset,length,aspects) in goldTriplets:
			uniqueAspectsByTopic.update(aspects)
	return uniqueAspectsByTopic

# return a dictionary where the keys are topics and the values are the aspect average precision for that topic...
def calculateAspectAveragePrecision(submissionDx,goldStdDx):
	averagePrecisionByTopic = {}	
	for topic in goldStdDx:
		aspectsFound = set()
		uniqueAspectsByTopic = findUniqueAspectsByTopic(topic)
		quartets = submissionDx.get(topic, [])
		quartets.sort() #sort the list by rank, then by pmid, then offset and then by length
		numerator = 0
		denominator = 0
		sumPrecision = 0.0
		count = 0
		debug("ASPECT FOR TOPIC:%d = %s" % (topic, str(uniqueAspectsByTopic)))
		for quartet in quartets:
			(relevantOffset, relevantChars, relevantAspects, goldPassage) = findRelevantCharsByTopic(quartet, topic)
			if relevantAspects:
				# only look at aspects that we have not yet seen...
				numNewAspects  = len(set(relevantAspects).difference(aspectsFound))
				if numNewAspects > 0:
					# all aspects at this rank get same numerator and denominator...
					numerator += 1
					denominator += 1
					sumPrecision +=numNewAspects*float(numerator)/float(denominator)
					debug("ASPECT TOPIC:%d NEW ASPECTS IN %s, %d of %d times %d" % (topic, str(relevantAspects), numerator, denominator, numNewAspects))
				else:
					# old aspects, but no new aspects, do not increase denominator...
					debug("ASPECT TOPIC:%d NO NEW ASPECTS IN %s" % (topic, str(relevantAspects)))
					pass
				# update aspects found list...
				aspectsFound.update(relevantAspects)
			else:
				# no aspects for this non-relevant passage...
				denominator += 1
				##debug("ASPECT TOPIC:%d NON-RELEVANT, %d of %d" % (topic, numerator, denominator))
		# compute average precision, divisor is the number of unique aspects for this topic,
		# this will automatically add in zeros for aspects not found...
		debug("ASPECT TOPIC:%d DID NOT RETRIEVE %d ASPECTS, MISSED %s" % (topic, len(uniqueAspectsByTopic) - len(aspectsFound), str(set(uniqueAspectsByTopic).difference(aspectsFound))))
		averagePrecisionByTopic[topic] = sumPrecision/len(uniqueAspectsByTopic)
	return averagePrecisionByTopic

# returns True of False depending on whether passage contains any relevant characters or not...
def checkForAnyRelevantChars(topic, pmid, runOffset, runLength):
	if not pmid in goldStdDx[topic]:
		return False
	else:
		runEnd = runOffset + runLength
		for (offset, length, aspects) in goldStdDx[topic][pmid]:
			end = offset + length
			if runOffset >= offset and runEnd <= end:
				# run is fully contained in quart passage...
				return True
			elif runOffset < offset and runEnd <= end and runEnd >= offset:
				# run starts before the quart and ends within the quart...
				return True
			elif  runOffset >= offset and runOffset <= end and runEnd > end:
				# run starts within the quart and ends beyond the quart...
				return True
			elif runOffset < offset and runEnd > end:
				# run starts before the quart and ends after the quart...
				return True
		return False	
	
# trackRelevantChars() has three possible return values:
# 	+1 means character was relevant and not previously seen
# 	-1 means character was not-relevant
# 	0 means character was relevant but was previously seen
def trackRelevantChars(topic, pmid, offset, topicGoldStdDx, trackingGoldStdDx):
	if pmid in topicGoldStdDx and offset in topicGoldStdDx[pmid]:
		# character is relevant, have we seen it before?		
		if offset in trackingGoldStdDx[pmid]:
			trackingGoldStdDx[pmid].remove(offset)
			return +1
		else:
			### sys.stderr.write("DUPLICATE RELEVANT CHARACTER\n")
			return 0			
	else:
		# character is not relevant...
		return -1
		
# return a dictionary where the keys are topics and the values are the passage average precision for that topic...
def calculatePassage2AveragePrecision(submissionDx, goldStdDx):
	averagePrecisionByTopic = {}	
	for topic in goldStdDx:
		# initialize...
		numerator = 0
		denominator = 0
		sumPrecision = 0.0
		topicGoldStdDx = {}
		trackingGoldStdDx = {}
		for pmid in goldStdDx[topic]:
			for (offset,length,aspects) in goldStdDx[topic][pmid]:
				r = range(offset, offset+length)
				topicGoldStdDx.setdefault(pmid, set()).update(r)
				trackingGoldStdDx.setdefault(pmid, set()).update(r)
		quartets = submissionDx.get(topic, [])
		quartets.sort() #sort the submission list by rank, then by pmid, then offset and then by length
		for quartet in quartets:
			# pass through each character, determining it's relevance...
			(rank, pmid, runOffset, runLength) = quartet
			# check for any relevant characters, this is not strictly necessary, but it does provide a significant
			# speedup, which is nice because the character-by-character accumulation is so slow...
			if not checkForAnyRelevantChars(topic, pmid, runOffset, runLength):
				# no relevant characters...
				for i in range(runLength):
					denominator += 1
			else:
				# some relevant characters...
				for offset in range(runOffset, runOffset+runLength):
					# three values:
					# 	+1 means character was relevant and not previously seen
					# 	-1 means character was not-relevant
					# 	0 means character was relevant but was previously seen
					val = trackRelevantChars(topic, pmid, offset, topicGoldStdDx, trackingGoldStdDx)
					if val != 0:
						# only count characters that have not been previously seen...
						denominator += 1
						if val == 1:				
							# only accumulate precision at relevant characters...
							numerator += 1
							sumPrecision += float(numerator)/float(denominator)
		# loop through trackingGoldStdDx counting the number of relevant characters, 
		# this is used as the denominator for average precision in order to effectively include zeros
		# for relevant characters that were not retrieved...
		count = 0
		for pmid in topicGoldStdDx:
			count += len(topicGoldStdDx[pmid])
		# note that this should be the same as the number of relevant characters found plus the number
		# of remaining characters in trackingGoldStdDx...
		### count2 = numerator
		### for pmid in trackingGoldStdDx:
		### 	count2 += len(trackingGoldStdDx[pmid])
		### assert(count == count2)	
		
		# compute the average precision for the topic...
		averagePrecisionByTopic[topic] = sumPrecision/count
	return averagePrecisionByTopic

# beginning of main program...

# check arguments...
if len(sys.argv) != 3:
	sys.stderr.write("usage:python %s [path-to-gold-standard-file] [glob-or-path-to-run-file] > STDOUT\n" % sys.argv[0])
	sys.exit(0)
	
# save paths...	
goldStandardFile = sys.argv[1]
submissionFileGlob = sys.argv[2]

# load gold standard data...
file = open(goldStandardFile, 'r')
goldStdDx = buildGoldStd(file)
file.close()

# output result header...
print '\t'.join(["RUN", "MEASURE", "TOPIC", "SCORE"])

# loop over submission files, which can be a multifile-glob...
for submissionFile in glob.glob(submissionFileGlob):
	# save run name as shortname of submission file...
	runName = (os.path.split(submissionFile)[1]).split('.')[0]
	# progress report...
	sys.stderr.write("Processing run %s..." % runName)
	# load submission data...
	file = open(submissionFile,'r')
	submissionDx = buildSubmissions(file)
	file.close()
	# compute topic scores...
	documentAveragePrecisionByTopic = calculateDocAveragePrecision(submissionDx,goldStdDx)
	passageAveragePrecisionByTopic = calculatePassageAveragePrecision(submissionDx,goldStdDx)
	aspectAveragePrecisionByTopic = calculateAspectAveragePrecision(submissionDx,goldStdDx)
	passage2AveragePrecisionByTopic = calculatePassage2AveragePrecision(submissionDx,goldStdDx)
	# compute final MAP's....
	documentMAP = sum(documentAveragePrecisionByTopic.values())/len(documentAveragePrecisionByTopic)
	passageMAP = sum(passageAveragePrecisionByTopic.values())/len(passageAveragePrecisionByTopic)
	aspectMAP = sum(aspectAveragePrecisionByTopic.values())/len(aspectAveragePrecisionByTopic)
	passage2MAP = sum(passage2AveragePrecisionByTopic.values())/len(passage2AveragePrecisionByTopic)
	# output document results...
	for topic in sorted(goldStdDx.keys()):
		print '\t'.join([runName, "DOCUMENT", str(topic), "%0.8f" % documentAveragePrecisionByTopic[topic]])
	print "%s" % '\t'.join([runName, "DOCUMENT", "MAP", "%0.8f" % documentMAP])
	# output passage results...
	for topic in sorted(goldStdDx.keys()):
		print '\t'.join([runName, "PASSAGE", str(topic), "%0.8f" % passageAveragePrecisionByTopic[topic]])
	print "%s" % '\t'.join([runName, "PASSAGE", "MAP", "%0.8f" % passageMAP])
	# output aspect results...
	for topic in sorted(goldStdDx.keys()):
		print '\t'.join([runName, "ASPECT", str(topic), "%0.8f" % aspectAveragePrecisionByTopic[topic]])
	print "%s" % '\t'.join([runName, "ASPECT", "MAP", "%0.8f" % aspectMAP])
	# output passage2 results...
	for topic in sorted(goldStdDx.keys()):
		print '\t'.join([runName, "PASSAGE2", str(topic), "%0.8f" % passage2AveragePrecisionByTopic[topic]])
	print "%s" % '\t'.join([runName, "PASSAGE2", "MAP", "%0.8f" % passage2MAP])
	# progress report...
	sys.stderr.write("OK.\n")

