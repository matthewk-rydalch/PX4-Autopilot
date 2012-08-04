import os
import glob

# path to global data files
base_path = '../orb/'
cfile = './sdlog_generated.h'
mfile_template = './mfile.template'

# there should be one LOGBROADCAST which gives the timing for the logging
logbroadcast_found = 0

# these types can nicely be imported into Matlab
allowed_types = ['uint8_t','int8_t','uint16_t','int16_t','uint32_t','int32_t','uint64_t','int64_t','float','double']

log_entries = []
# loop through global_data_files ending in _t.h and look for LOGME (per variable) and LOGBROADCAST (overall)
for path in glob.glob( os.path.join(base_path, '*_t.h') ):
    # filename is supposed to be global_data_bapedibup_t.h
    if 'global_data' not in path:   
        print 'path: ' + path
        raise 'wrong filename found'
    f = open(path, 'r')
    access_conf_found = False;
    # strip away ../../../../apps/orb/ and _t.h
    data_name = path.lstrip(base_path)[0:-4]
    # strip away ../../../../apps/orb/ and global_data_ and _t.h
    name = path.lstrip(base_path)[12:-4]
    log_entry = {'data_name': data_name,'name':name,'vars': []}
    
    logbroadcast = False;
    
    # loop throug lines
    for line in f:
    
        line_parts = line.split()
        # access_conf is needed to lock the data
        if 'access_conf_t' in line:
            
            # always use the access_conf which has the LOGBROADCAST flag
            if 'LOGBROADCAST' in line:
                access_conf_found = True
                log_entry['access_conf_name'] = line_parts[1].rstrip(';')
                logbroadcast = True
                print 'LOGBROADCAST found in ' + data_name
                logbroadcast_found += 1
            # but use an access_conf anyway 
            elif access_conf_found == False:
                access_conf_found = True
                log_entry['access_conf_name'] = line_parts[1].rstrip(';')
        # variables flagged with LOGME should be logged
        elif 'LOGME' in line:
            var_entry = {'type': line_parts[0]}
        
            # check that it is an allowed type
            if var_entry['type'] not in allowed_types:
                print 'file: '+ path + ', type: ' + var_entry['type']
                raise 'unsupported type'
            
            # save variable name and number for array
            if '[' in line_parts[1]:
                var_entry['name'] = line_parts[1].split('[')[0]
                var_entry['number'] = line_parts[1].split('[')[1].rstrip('];')
            else:
                var_entry['name'] = line_parts[1].rstrip(';')
                var_entry['number'] = 1
                
            # add the variable
            log_entry['vars'].append(var_entry)
    # only use the global data file if any variables have a LOGME
    if logbroadcast == True and len(log_entry['vars']) > 0:
        logbroadcast_entry = log_entry
    elif len(log_entry['vars']) > 0:
        print 'added ' + log_entry['data_name']
        log_entries.append(log_entry)
    f.close()

# check that we have one and only one LOGBROADCAST
if logbroadcast_found > 1:
    raise 'too many LOGBROADCAST found\n'
elif logbroadcast_found == 0:
    raise 'no LOGBROADCAST found\n'

# write function to c file

header = '/* This file is autogenerated in nuttx/configs/px4fmu/include/updatesdlog.py */\n\
\n\
#ifndef SDLOG_GENERATED_H_\n\
#define SDLOG_GENERATED_H_\n\
\n\
\n\
'

cstruct = 'typedef struct\n{\n'

for j in logbroadcast_entry['vars']:
    cstruct += '\t' + j['type'] + ' ' + logbroadcast_entry['name'] + '_' + j['name']
    if j['number'] == 1:
        cstruct += ';\n'
    else:
        cstruct += '[' + j['number'] + '];\n'

for i in log_entries:
    for j in i['vars']:
        cstruct += '\t' + j['type'] + ' ' + i['name'] + '_' + j['name']
        if j['number'] == 1:
            cstruct += ';\n'
        else:
            cstruct += '[' + j['number'] + '];\n'

cstruct += '\tchar check[4];\n} __attribute__((__packed__)) log_block_t;\n\n'


copy_function = 'void copy_block(log_block_t* log_block)\n{\n'
copy_function += '\tif(global_data_wait(&' + logbroadcast_entry['data_name'] + '->' + logbroadcast_entry['access_conf_name'] + ') == 0)\n\t{\n'

for j in logbroadcast_entry['vars']:
    copy_function += '\t\tmemcpy(&log_block->' + logbroadcast_entry['name'] + '_' + j['name'] + ',&' + logbroadcast_entry['data_name'] + '->' + j['name'] + ',sizeof(' + j['type'] + ')*' + str(j['number']) + ');\n'
    #copy_function += '\t\t}\n'

# generate logging MACRO


for i in log_entries:
    copy_function += '\t\tif(global_data_trylock(&' + i['data_name'] + '->' + i['access_conf_name'] + ') == 0)\n\t\t{\n'
    
    for j in i['vars']:
        copy_function += '\t\t\tmemcpy(&log_block->' + i['name'] + '_' + j['name'] + ',&' + i['data_name'] + '->' + j['name'] + ',sizeof(' + j['type'] + ')*' + str(j['number']) + ');\n'
        
    copy_function += '\t\t\tglobal_data_unlock(&' + i['data_name'] + '->' + i['access_conf_name'] + ');\n'
    copy_function += '\t\t}\n'
copy_function += '\t\tglobal_data_unlock(&' + logbroadcast_entry['data_name'] + '->' + logbroadcast_entry['access_conf_name'] + ');\n'
copy_function += '\t}\n'

copy_function += '}\n'

footer = '\n#endif'



# generate mfile

type_bytes = {
'uint8_t' : 1,
'int8_t' : 1,
'uint16_t' : 2,
'int16_t' : 2,
'uint32_t' : 4,
'int32_t' : 4,
'uint64_t' : 8,
'int64_t' : 8,
'float' : 4,
'double' : 8,
}

type_names_matlab = {
'uint8_t' : 'uint8',
'int8_t' : 'int8',
'uint16_t' : 'uint16',
'int16_t' : 'int16',
'uint32_t' : 'uint32',
'int32_t' : 'int32',
'uint64_t' : 'uint64',
'int64_t' : 'int64',
'float' : 'float',
'double' : 'double',
}


# read template mfile
mf = open(mfile_template, 'r')
mfile_template_string = mf.read()

mfile_define = '#define MFILE_STRING "% This file is autogenerated in updatesdlog.py and mfile.template in apps/sdlog\\n\\\n'
mfile_define += '%% Define logged values \\n\\\n\\n\\\nlogTypes = {};\\n\\\n'

for j in logbroadcast_entry['vars']:
    mfile_define += 'logTypes{end+1} = struct(\'data\',\'' + logbroadcast_entry['name'] + '\',\'variable_name\',\'' + j['name'] + '\',\'type_name\',\'' + type_names_matlab.get(j['type']) + '\',\'type_bytes\',' + str(type_bytes.get(j['type'])) + ',\'number_of_array\',' + str(j['number']) + ');\\n\\\n'

for i in log_entries:
    for j in i['vars']:
        mfile_define += 'logTypes{end+1} = struct(\'data\',\'' + i['name'] + '\',\'variable_name\',\'' + j['name'] + '\',\'type_name\',\'' + type_names_matlab.get(j['type']) + '\',\'type_bytes\',' + str(type_bytes.get(j['type'])) + ',\'number_of_array\',' + str(j['number']) + ');\\n\\\n'
        


mfile_define += '\\\n' + mfile_template_string.replace('\n', '\\n\\\n').replace('\"','\\\"') + '"'


# write to c File
cf = open(cfile, 'w')
cf.write(header)
cf.write(cstruct);
cf.write(copy_function)

cf.write(mfile_define)

cf.write(footer)
cf.close()

print 'finished, cleanbuild needed!'
