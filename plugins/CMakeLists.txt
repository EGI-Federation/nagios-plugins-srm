cmake_minimum_required(VERSION 2.8)

file (GLOB srm_probe *.py)

install (FILES ${srm_probe}
         DESTINATION usr/lib${LIB_SUFFIX}/nagios/plugins/srm/
         PERMISSIONS OWNER_EXECUTE OWNER_WRITE OWNER_READ
                     GROUP_EXECUTE GROUP_READ
                     WORLD_EXECUTE WORLD_READ
)

